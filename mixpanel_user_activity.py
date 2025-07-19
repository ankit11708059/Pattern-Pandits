import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import base64
import os
import ssl
import urllib3
from dotenv import load_dotenv
import subprocess
import asyncio
from typing import Optional
import openai
import tempfile
import shutil
from openai import OpenAI

# ---------------------------------------------------------------------------
# Disable SSL verification globally (work-around for self-signed certificates)
# ---------------------------------------------------------------------------
from network_utils import install_insecure_ssl

install_insecure_ssl()

import httpx

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables
load_dotenv()

# Mixpanel API configuration
MIXPANEL_PROJECT_ID = os.getenv("MIXPANEL_PROJECT_ID")
MIXPANEL_USERNAME = os.getenv("MIXPANEL_USERNAME")  # Service account username
MIXPANEL_SECRET = os.getenv("MIXPANEL_SECRET")      # Service account secret

# OpenAI configuration for Cursor-like AI assistance
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY


class MixpanelUserActivity:
    def __init__(self, project_id, username, secret):
        self.project_id = project_id
        self.username = username
        self.secret = secret
        # Using the correct India Query API endpoint
        self.base_url = "https://in.mixpanel.com/api"
        
        # Create session with SSL verification disabled
        self.session = requests.Session()
        self.session.verify = False
        
        # Configure SSL context for fallback
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        except Exception as e:
            st.warning(f"SSL context configuration warning: {e}")
    
    def get_user_activity(self, distinct_ids, from_date, to_date):
        """Get user activity data from Mixpanel Profile Event Activity API"""
        if not self.project_id:
            return {"error": "Project ID not configured"}
        
        if not self.username or not self.secret:
            return {"error": "Username and secret not configured"}
        
        # Format distinct_ids as JSON array string
        if isinstance(distinct_ids, list):
            distinct_ids_str = json.dumps(distinct_ids)
        else:
            distinct_ids_str = json.dumps([distinct_ids])
        
        # Use the correct API endpoint
        url = f"{self.base_url}/query/stream/query"
        params = {
            "project_id": self.project_id,
            "distinct_ids": distinct_ids_str,
            "from_date": from_date,
            "to_date": to_date
        }
        
        try:
            # Use Basic Authentication with service account credentials
            response = self.session.get(
                url, 
                params=params, 
                auth=(self.username, self.secret),  # Basic Auth with username and secret
                headers={'accept': 'application/json'},  # Add accept header
                timeout=30
            )
            
            # Debug information
            st.write(f"🔍 **Debug Info:**")
            st.write(f"- URL: {url}")
            st.write(f"- Project ID: {self.project_id}")
            st.write(f"- Username: {self.username}")
            st.write(f"- Response Status: {response.status_code}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.SSLError as e:
            st.error(f"SSL Error: {e}")
            return {"error": f"SSL Error: {e}"}
        except requests.exceptions.RequestException as e:
            st.error(f"API request failed: {e}")
            # Show response text for debugging
            try:
                st.error(f"Response text: {response.text}")
            except:
                pass
            return {"error": f"API request failed: {e}"}
        except json.JSONDecodeError as e:
            st.error(f"JSON decode error: {e}")
            return {"error": f"JSON decode error: {e}"}
    
    def format_activity_data(self, api_response):
        """Format API response into a pandas DataFrame"""
        if "error" in api_response:
            return pd.DataFrame()
        
        # The Profile Event Activity API returns data in a different format
        if "results" not in api_response:
            st.write("API Response structure:", api_response.keys() if isinstance(api_response, dict) else type(api_response))
            return pd.DataFrame()
        
        all_events = []
        
        # Handle the actual response structure from Profile Event Activity API
        results = api_response["results"]
        if isinstance(results, dict):
            for user_id, events in results.items():
                if isinstance(events, list):
                    for event in events:
                        # Robust timestamp parsing
                        def _parse_mixpanel_time(raw_time):
                            """Convert Mixpanel raw time to datetime.

                            Handles seconds (10-digit) or milliseconds (13-digit) epoch values.
                            Returns NaT if value is missing/invalid.
                            """
                            try:
                                if raw_time is None:
                                    return pd.NaT
                                ts = int(raw_time)
                                # If ms ( > year 33658 ), convert to seconds
                                if ts > 1e12:
                                    ts = ts / 1000
                                return datetime.fromtimestamp(ts)
                            except Exception:
                                return pd.NaT

                        raw_time = (
                            event.get("time")
                            or event.get("properties", {}).get("time")
                            or event.get("properties", {}).get("$time")
                        )

                        event_data = {
                            "user_id": user_id,
                            "event": event.get("event", ""),
                            "time": _parse_mixpanel_time(raw_time),
                            "properties": json.dumps(event.get("properties", {}), indent=2)
                        }
                        
                        # Add some key properties as separate columns
                        props = event.get("properties", {})
                        event_data["platform"] = props.get("platform", "")
                        event_data["browser"] = props.get("browser", "")
                        event_data["city"] = props.get("$city", "")
                        event_data["country"] = props.get("$country_code", "")
                        
                        all_events.append(event_data)
        
        if not all_events:
            return pd.DataFrame()
        
        df = pd.DataFrame(all_events)
        df = df.sort_values("time", ascending=False)
        return df

def main():
    st.set_page_config(
        page_title="Mixpanel User Activity Tracker",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Mixpanel User Activity Tracker")
    st.markdown("Track and analyze user activity data from Mixpanel")
    
    # Check if credentials are configured
    if not MIXPANEL_PROJECT_ID or not MIXPANEL_USERNAME or not MIXPANEL_SECRET:
        st.error("⚠️ Mixpanel credentials not configured!")
        st.markdown("""
        Please add the following to your `.env` file:
        ```
        MIXPANEL_PROJECT_ID=your_project_id
        MIXPANEL_USERNAME=your_service_account_username
        MIXPANEL_SECRET=your_service_account_secret
        ```
        """)
        return
    
    # Initialize Mixpanel client
    client = MixpanelUserActivity(MIXPANEL_PROJECT_ID, MIXPANEL_USERNAME, MIXPANEL_SECRET)
    
    # Single Data Query tab (AI assistant removed)
    st.header("📊 Data Query")
    render_data_query_tab(client)

def render_data_query_tab(client):
    """Render the original data query interface"""
    # Sidebar for configuration
    st.sidebar.header("🔧 Configuration")
    
    # User ID input
    user_ids_input = st.sidebar.text_area(
        "User IDs (one per line)",
        placeholder="Enter user IDs, one per line...",
        height=100
    )
    
    # Date range selection
    col1, col2 = st.sidebar.columns(2)
    with col1:
        from_date = st.date_input(
            "From Date",
            value=datetime.now() - timedelta(days=7),
            max_value=datetime.now().date()
        )
    
    with col2:
        to_date = st.date_input(
            "To Date",
            value=datetime.now().date(),
            max_value=datetime.now().date()
        )
    
    # Query button
    if st.sidebar.button("🔍 Get User Activity", type="primary"):
        if not user_ids_input.strip():
            st.error("Please enter at least one user ID")
            return
        
        # Parse user IDs
        user_ids = [uid.strip() for uid in user_ids_input.strip().split('\n') if uid.strip()]
        
        if not user_ids:
            st.error("Please enter valid user IDs")
            return
        
        # Show loading spinner
        with st.spinner("Fetching user activity data..."):
            # Get activity data
            response = client.get_user_activity(
                distinct_ids=user_ids,
                from_date=from_date.strftime("%Y-%m-%d"),
                to_date=to_date.strftime("%Y-%m-%d")
            )
            
            if "error" in response:
                st.error(f"Error: {response['error']}")
                return
            
            # Format data
            df = client.format_activity_data(response)
            
            if df.empty:
                st.warning("No activity data found for the specified users and date range.")
                return
            
            # Display results
            st.success(f"✅ Found {len(df)} events for {len(user_ids)} user(s)")
            
            # Metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Events", len(df))
            with col2:
                st.metric("Unique Users", df['user_id'].nunique())
            with col3:
                st.metric("Unique Events", df['event'].nunique())
            with col4:
                st.metric("Date Range", f"{from_date} to {to_date}")
            
            # Event timeline chart
            if len(df) > 0:
                st.subheader("📈 Event Timeline")
                
                # Group by date for timeline
                df['date'] = df['time'].dt.date
                daily_counts = df.groupby('date').size().reset_index(name='count')
                
                st.line_chart(daily_counts.set_index('date'))
                
                # Top events
                st.subheader("🔥 Top Events")
                event_counts = df['event'].value_counts().head(10)
                st.bar_chart(event_counts)
            
            # Activity data table
            st.subheader("📋 Activity Data")
            
            # Optional user filter only
            selected_users = st.multiselect(
                "Filter by Users",
                options=df['user_id'].unique(),
                default=df['user_id'].unique()
            )

            # Apply user filter
            filtered_df = df[df['user_id'].isin(selected_users)]

            # Ensure latest events appear at the top
            filtered_df = filtered_df.sort_values("time", ascending=False)
            
            # Enrich with descriptions & summarise session
            from rag_utils import enrich_with_event_desc, summarize_session

            filtered_df = enrich_with_event_desc(filtered_df)

            # Display enriched table
            st.dataframe(
                filtered_df[['time', 'event', 'event_desc', 'user_id', 'platform', 'city', 'country']],
                use_container_width=True
            )

            # RAG summary
            st.subheader("📝 Session Summary (AI)")
            with st.spinner("Generating summary …"):
                summary_text = summarize_session(filtered_df)
            st.markdown(summary_text)
            
            # Export functionality
            if st.button("📥 Export to CSV"):
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"mixpanel_activity_{from_date}_{to_date}.csv",
                    mime="text/csv"
                )

if __name__ == "__main__":
    main() 