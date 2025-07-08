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
from cursor_agent import CursorBackgroundAgent

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

class CursorAssistant:
    """AI assistant that can interact with the codebase like Cursor"""
    
    def __init__(self, project_path: str = "."):
        self.project_path = project_path
        self.context_files = []
        
    def read_file(self, file_path: str) -> str:
        """Read a file from the project"""
        try:
            full_path = os.path.join(self.project_path, file_path)
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            return f"Error reading file {file_path}: {str(e)}"
    
    def search_code(self, query: str) -> list:
        """Search for code patterns in the project"""
        results = []
        try:
            # Use grep to search for patterns
            result = subprocess.run(
                ['grep', '-r', '-n', query, self.project_path],
                capture_output=True,
                text=True
            )
            
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines[:10]:  # Limit to first 10 results
                    if ':' in line:
                        file_path, line_num, content = line.split(':', 2)
                        results.append({
                            'file': file_path.replace(self.project_path + '/', ''),
                            'line': line_num,
                            'content': content.strip()
                        })
        except Exception as e:
            results.append({'error': str(e)})
        
        return results
    
    def list_files(self, directory: str = ".") -> list:
        """List files in a directory"""
        try:
            full_path = os.path.join(self.project_path, directory)
            files = []
            for root, dirs, filenames in os.walk(full_path):
                # Skip hidden directories and common ignore patterns
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', '.git']]
                
                for filename in filenames:
                    if not filename.startswith('.') and not filename.endswith('.pyc'):
                        rel_path = os.path.relpath(os.path.join(root, filename), self.project_path)
                        files.append(rel_path)
            
            return sorted(files)[:50]  # Limit to first 50 files
        except Exception as e:
            return [f"Error listing files: {str(e)}"]
    
    def get_ai_response(self, query: str, context: str = "") -> str:
        """Get AI response using OpenAI API (similar to Cursor's AI)"""
        if not OPENAI_API_KEY:
            return "OpenAI API key not configured. Please add OPENAI_API_KEY to your .env file."
        
        try:
            system_prompt = f"""You are an AI coding assistant similar to Cursor. You have access to the user's codebase and can help with:
1. Code analysis and explanation
2. Debugging and troubleshooting
3. Code suggestions and improvements
4. File navigation and understanding
5. Mixpanel data analysis integration

Current project context: {context}

Respond helpfully and provide specific code examples when relevant."""

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"Error getting AI response: {str(e)}"

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
                        event_data = {
                            "user_id": user_id,
                            "event": event.get("event", ""),
                            "time": datetime.fromtimestamp(event.get("time", 0)),
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
    
    # Initialize Cursor assistant (for reading files)
    cursor_assistant = CursorAssistant(project_path=os.getcwd())
    
    # Initialize Cursor background agent (for executing commands)
    cursor_agent = CursorBackgroundAgent(project_path=os.getcwd())
    
    # Create tabs for different functionalities
    tab1, tab2 = st.tabs(["📊 Data Query", "💬 AI Chat Assistant"])
    
    with tab1:
        # Original data query functionality
        render_data_query_tab(client)
    
    with tab2:
        # New chat interface with full Cursor integration
        render_chat_tab(client, cursor_assistant, cursor_agent)

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
            
            # Add filters
            col1, col2 = st.columns(2)
            with col1:
                selected_events = st.multiselect(
                    "Filter by Events",
                    options=df['event'].unique(),
                    default=df['event'].unique()
                )
            
            with col2:
                selected_users = st.multiselect(
                    "Filter by Users",
                    options=df['user_id'].unique(),
                    default=df['user_id'].unique()
                )
            
            # Apply filters
            filtered_df = df[
                (df['event'].isin(selected_events)) & 
                (df['user_id'].isin(selected_users))
            ]
            
            # Display filtered data
            st.dataframe(
                filtered_df[['time', 'user_id', 'event', 'platform', 'browser', 'city', 'country']],
                use_container_width=True
            )
            
            # Export functionality
            if st.button("📥 Export to CSV"):
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"mixpanel_activity_{from_date}_{to_date}.csv",
                    mime="text/csv"
                )

def render_chat_tab(client, cursor_assistant: CursorAssistant, cursor_agent: CursorBackgroundAgent):
    """Render the AI chat interface"""
    st.header("💬 AI Chat Assistant")
    st.markdown("Ask questions about your **Mixpanel data** or execute **real Cursor commands**!")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hi! I'm your integrated AI assistant with **real Cursor capabilities**. I can help you with:\n\n📊 **Mixpanel Data Analysis**\n- User activity tracking\n- Event analysis\n- Data insights\n\n🤖 **Cursor Development Actions**\n- Create files and code\n- Make code modifications\n- Execute terminal commands\n- Create pull requests\n- Deploy applications\n\n💬 **Example Commands:**\n- `cursor create file test.py`\n- `run streamlit run app.py`\n- `pr create`\n- `deploy streamlit`\n\nWhat would you like to do?"}
        ]
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me about Mixpanel data or execute Cursor commands..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate assistant response
        with st.chat_message("assistant"):
            with st.spinner("Executing..."):
                response = process_chat_message(prompt, client, cursor_assistant, cursor_agent)
                st.markdown(response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Quick action buttons
    st.markdown("### 🚀 Quick Actions")
    
    # Mixpanel actions
    st.markdown("**📊 Mixpanel Actions:**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Get User Summary"):
            user_id = st.text_input("Enter User ID:", key="summary_user_id")
            if user_id:
                response = get_user_summary(user_id, client)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()
    
    with col2:
        if st.button("🔥 Top Events Today"):
            response = get_top_events_today(client)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col3:
        if st.button("📈 Activity Trends"):
            response = get_activity_trends(client)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    # Cursor read-only actions
    st.markdown("**🔍 Cursor Read Actions:**")
    col4, col5, col6 = st.columns(3)
    
    with col4:
        if st.button("📁 List Files"):
            response = handle_file_list_query("list files", cursor_assistant)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col5:
        if st.button("🔍 Search Code"):
            search_term = st.text_input("Search term:", key="search_term")
            if search_term:
                response = handle_code_search_query(f"search {search_term}", cursor_assistant)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()
    
    with col6:
        if st.button("📄 Read File"):
            filename = st.text_input("Filename:", key="read_filename")
            if filename:
                response = handle_file_read_query(f"read {filename}", cursor_assistant)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()
    
    # Cursor action buttons (real commands)
    st.markdown("**⚡ Cursor Action Commands:**")
    col7, col8, col9 = st.columns(3)
    
    with col7:
        if st.button("🎯 Deploy App"):
            response = handle_cursor_agent_command("deploy streamlit", cursor_agent)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col8:
        if st.button("📝 Create File"):
            filename = st.text_input("New filename:", key="create_filename")
            if filename:
                response = handle_cursor_agent_command(f"create file {filename}", cursor_agent)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()
    
    with col9:
        if st.button("🔧 Run Command"):
            command = st.text_input("Terminal command:", key="run_command")
            if command:
                response = handle_cursor_agent_command(f"run {command}", cursor_agent)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()
    
    # Command history
    st.markdown("### 📜 Command History")
    if st.button("Show Command History"):
        history = cursor_agent.get_command_history()
        if history:
            history_text = "## Recent Commands:\n\n"
            for i, cmd in enumerate(history[-10:], 1):  # Show last 10 commands
                history_text += f"{i}. **{cmd['command']}** - {cmd['timestamp']}\n"
            st.session_state.messages.append({"role": "assistant", "content": history_text})
            st.rerun()
        else:
            st.info("No commands executed yet")

def process_chat_message(message: str, client: MixpanelUserActivity, cursor_assistant: CursorAssistant, cursor_agent: CursorBackgroundAgent) -> str:
    """Process chat message and return AI response"""
    message_lower = message.lower()
    
    # Check for background agent commands (real Cursor actions)
    if any(keyword in message_lower for keyword in ["cursor", "create", "modify", "edit", "pr", "pull request", "run", "execute", "fix", "debug", "deploy", "build"]):
        return handle_cursor_agent_command(message, cursor_agent)
    # Check for Cursor-like development queries (read-only)
    elif any(keyword in message_lower for keyword in ["file", "code", "function", "class", "import", "error", "bug"]):
        return handle_cursor_query(message, cursor_assistant)
    elif "read" in message_lower and any(ext in message_lower for ext in [".py", ".js", ".ts", ".html", ".css", ".json"]):
        return handle_file_read_query(message, cursor_assistant)
    elif "search" in message_lower and "code" in message_lower:
        return handle_code_search_query(message, cursor_assistant)
    elif "list" in message_lower and ("files" in message_lower or "directory" in message_lower):
        return handle_file_list_query(message, cursor_assistant)
    # Mixpanel-specific queries
    elif "user" in message_lower and ("activity" in message_lower or "events" in message_lower):
        return handle_user_activity_query(message, client)
    elif "summary" in message_lower:
        return handle_summary_query(message, client)
    elif "top events" in message_lower or "popular events" in message_lower:
        return get_top_events_today(client)
    elif "trend" in message_lower or "pattern" in message_lower:
        return get_activity_trends(client)
    elif "help" in message_lower:
        return get_help_message()
    else:
        return generate_general_response(message, client, cursor_assistant)

def handle_cursor_agent_command(message: str, cursor_agent: CursorBackgroundAgent) -> str:
    """Handle real Cursor agent commands that can make changes"""
    
    try:
        # Execute the command using the background agent
        result = cursor_agent.execute_command(message)
        
        if result.get("success"):
            response = f"## ✅ Command Executed Successfully\n\n"
            
            # Handle different types of successful results
            if "message" in result:
                response += f"**Result:** {result['message']}\n\n"
            
            if "ai_response" in result:
                response += f"**AI Response:**\n{result['ai_response']}\n\n"
            
            if "content" in result:
                response += f"**Generated Content:**\n```\n{result['content'][:500]}{'...' if len(result['content']) > 500 else ''}\n```\n\n"
            
            if "stdout" in result:
                response += f"**Output:**\n```\n{result['stdout']}\n```\n\n"
            
            if "stderr" in result and result["stderr"]:
                response += f"**Warnings:**\n```\n{result['stderr']}\n```\n\n"
            
            if "pr_url" in result:
                response += f"**Pull Request:** {result['pr_url']}\n\n"
            
            if "path" in result:
                response += f"**File Path:** {result['path']}\n\n"
            
            # Add action suggestions
            response += "💡 **What's next?**\n"
            response += "- Type `cursor open <filename>` to view the file\n"
            response += "- Type `run <command>` to execute terminal commands\n"
            response += "- Type `pr create` to create a pull request\n"
            
            return response
            
        else:
            error_msg = result.get("error", "Unknown error occurred")
            return f"""
## ❌ Command Failed

**Error:** {error_msg}

💡 **Try these alternatives:**
- Check the command syntax
- Ensure required environment variables are set
- Use `help` to see available commands
            """
    
    except Exception as e:
        return f"""
## ❌ Command Execution Error

**Error:** {str(e)}

💡 **Troubleshooting:**
- Check if the command is properly formatted
- Ensure you have the necessary permissions
- Try a simpler command first
        """

def handle_cursor_query(message: str, cursor_assistant: CursorAssistant) -> str:
    """Handle Cursor-like development queries"""
    # Get AI response with code context
    context = f"Project files: {cursor_assistant.list_files()[:10]}"
    response = cursor_assistant.get_ai_response(message, context)
    
    return f"""
## 🤖 Cursor AI Assistant

{response}

💡 **Available Commands:**
- `read <filename>` - Read a specific file
- `search <pattern>` - Search for code patterns
- `list files` - List project files
- Ask about code, functions, classes, errors, etc.
    """

def handle_file_read_query(message: str, cursor_assistant: CursorAssistant) -> str:
    """Handle file reading queries"""
    # Extract filename from message
    words = message.split()
    filename = None
    
    for word in words:
        if any(ext in word for ext in ['.py', '.js', '.ts', '.html', '.css', '.json', '.md', '.txt']):
            filename = word.strip('",.:')
            break
    
    if filename:
        content = cursor_assistant.read_file(filename)
        return f"""
## 📄 File: {filename}

```python
{content[:2000]}{"..." if len(content) > 2000 else ""}
```

💡 **Tip:** Ask me questions about this file or request specific parts!
        """
    else:
        return "Please specify a filename to read. Example: 'read mixpanel_user_activity.py'"

def handle_code_search_query(message: str, cursor_assistant: CursorAssistant) -> str:
    """Handle code search queries"""
    # Extract search term
    words = message.split()
    search_term = None
    
    for i, word in enumerate(words):
        if word.lower() in ["search", "find"] and i + 1 < len(words):
            search_term = words[i + 1].strip('",.:')
            break
    
    if search_term:
        results = cursor_assistant.search_code(search_term)
        
        if not results:
            return f"No results found for '{search_term}'"
        
        response = f"## 🔍 Search Results for '{search_term}'\n\n"
        
        for result in results[:5]:  # Show first 5 results
            if 'error' in result:
                response += f"❌ {result['error']}\n"
            else:
                response += f"**{result['file']}:{result['line']}**\n```\n{result['content']}\n```\n\n"
        
        return response
    else:
        return "Please specify a search term. Example: 'search MixpanelUserActivity'"

def handle_file_list_query(message: str, cursor_assistant: CursorAssistant) -> str:
    """Handle file listing queries"""
    files = cursor_assistant.list_files()
    
    if not files:
        return "No files found in the project directory."
    
    response = "## 📁 Project Files\n\n"
    
    # Group files by extension
    file_groups = {}
    for file in files:
        ext = os.path.splitext(file)[1] or 'no extension'
        if ext not in file_groups:
            file_groups[ext] = []
        file_groups[ext].append(file)
    
    for ext, file_list in sorted(file_groups.items()):
        response += f"**{ext} files:**\n"
        for file in file_list[:10]:  # Show first 10 files per extension
            response += f"- {file}\n"
        if len(file_list) > 10:
            response += f"... and {len(file_list) - 10} more\n"
        response += "\n"
    
    return response

def handle_user_activity_query(message: str, client: MixpanelUserActivity) -> str:
    """Handle user activity related queries"""
    # Extract user ID if mentioned
    words = message.split()
    user_id = None
    
    for i, word in enumerate(words):
        if word.lower() in ["user", "id"] and i + 1 < len(words):
            user_id = words[i + 1].strip('",.:')
            break
    
    if user_id:
        return get_user_summary(user_id, client)
    else:
        return "Please specify a user ID to get activity data. For example: 'Show me activity for user abc123'"

def handle_summary_query(message: str, client: MixpanelUserActivity) -> str:
    """Handle summary queries"""
    return """
    I can provide various summaries:
    
    📊 **User Summary**: Get detailed activity for a specific user
    📈 **Activity Trends**: See overall activity patterns
    🔥 **Top Events**: Most popular events today
    🌍 **Geographic Distribution**: Where your users are located
    
    What type of summary would you like?
    """

def get_user_summary(user_id: str, client: MixpanelUserActivity) -> str:
    """Get summary for a specific user"""
    try:
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        
        response = client.get_user_activity([user_id], from_date, to_date)
        
        if "error" in response:
            return f"❌ Error getting data for user {user_id}: {response['error']}"
        
        df = client.format_activity_data(response)
        
        if df.empty:
            return f"📭 No activity found for user {user_id} in the last 7 days."
        
        user_df = df[df['user_id'] == user_id]
        
        return f"""
## 👤 User Summary: {user_id}

**📊 Activity Overview (Last 7 days):**
- Total Events: {len(user_df)}
- Unique Event Types: {user_df['event'].nunique()}
- First Activity: {user_df['time'].min()}
- Last Activity: {user_df['time'].max()}

**🔥 Top Events:**
{user_df['event'].value_counts().head(5).to_string()}

**🌍 Location:**
- City: {user_df['city'].mode().iloc[0] if not user_df['city'].mode().empty else 'Unknown'}
- Country: {user_df['country'].mode().iloc[0] if not user_df['country'].mode().empty else 'Unknown'}

**💻 Platform:**
- Primary Platform: {user_df['platform'].mode().iloc[0] if not user_df['platform'].mode().empty else 'Unknown'}
        """
    except Exception as e:
        return f"❌ Error analyzing user {user_id}: {str(e)}"

def get_top_events_today(client: MixpanelUserActivity) -> str:
    """Get top events for today"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get sample data for today (you might want to modify this to get all users)
        response = client.get_user_activity(["sample"], today, today)
        
        return f"""
## 🔥 Top Events Today ({today})

📊 **Event Activity:**
- Most events typically occur during business hours
- User engagement patterns vary by platform
- Mobile events tend to peak in the evening

💡 **Tip:** Use the Data Query tab to get specific event data for your users!
        """
    except Exception as e:
        return f"❌ Error getting today's events: {str(e)}"

def get_activity_trends(client: MixpanelUserActivity) -> str:
    """Get activity trends"""
    return """
## 📈 Activity Trends Analysis

**🕐 Typical Patterns:**
- Morning peaks (9-11 AM)
- Afternoon activity (2-4 PM)
- Evening engagement (7-9 PM)

**📱 Platform Trends:**
- Mobile usage increases in evenings
- Desktop activity peaks during work hours
- Weekend patterns differ from weekdays

**🌍 Geographic Insights:**
- Activity follows timezone patterns
- Regional preferences vary by feature

💡 **Tip:** Use the Data Query tab with specific date ranges to see your actual trends!
    """

def get_help_message() -> str:
    """Get help message"""
    return """
## 🤖 Integrated AI Assistant with Real Cursor Capabilities

### 📊 **Mixpanel Data Analysis:**

🔍 **User Analysis:**
- "Show me activity for user abc123"
- "Get summary for user xyz789"
- "What events did user 123 perform?"

📈 **Data Insights:**
- "What are the top events today?"
- "Show me activity trends"
- "Analyze user behavior patterns"

### 🔍 **Cursor Read Operations:**

📁 **File Operations:**
- "list files" - See all project files
- "read mixpanel_user_activity.py" - Read a specific file
- "search MixpanelUserActivity" - Search for code patterns

🔧 **Code Analysis:**
- "Explain this function"
- "Help me debug this error"
- "How does this class work?"
- "What imports do I need?"

### ⚡ **Cursor Action Commands (Real Execution):**

🎯 **File Creation:**
- "cursor create file test.py" - Create a new file with AI-generated content
- "create component Button.jsx" - Create a React component
- "create function calculate_metrics" - Create a specific function

🔧 **Code Modification:**
- "modify add error handling to function X"
- "edit optimize this code block"
- "fix bug in authentication flow"

📦 **Project Management:**
- "run pip install requests" - Execute terminal commands
- "run streamlit run app.py" - Start applications
- "deploy streamlit" - Deploy your Streamlit app

🚀 **Git Operations:**
- "pr create" - Create a pull request with current changes
- "run git status" - Check git status
- "run git add ." - Stage all changes

🐛 **Debugging & Fixing:**
- "fix import error in main.py"
- "debug connection timeout issue"
- "run python -m pytest" - Run tests

### 💬 **Natural Language Commands:**

**Examples:**
- "cursor create a new API endpoint for user data"
- "run the tests and show me the results"
- "create a pull request for the new feature"
- "deploy the app to production"
- "fix the authentication bug"

### 🔐 **Required Environment Variables:**

For full functionality, add these to your `.env` file:
```
# Mixpanel
MIXPANEL_PROJECT_ID=your_project_id
MIXPANEL_USERNAME=your_username
MIXPANEL_SECRET=your_secret

# AI Features
OPENAI_API_KEY=your_openai_key

# GitHub Integration
GITHUB_TOKEN=your_github_token
```

### 🚀 **Quick Actions:**
Use the buttons below for common tasks, or type commands directly in the chat!

**💡 Pro Tips:**
- Commands starting with "cursor", "create", "modify", "run", "pr", "deploy" will execute real actions
- Other queries will provide information and analysis
- Check the Command History to see what you've executed
    """

def generate_general_response(message: str, client: MixpanelUserActivity, cursor_assistant: CursorAssistant) -> str:
    """Generate a general response with both Mixpanel and Cursor context"""
    
    # Try to get AI response if OpenAI is configured
    if OPENAI_API_KEY:
        # Get some project context
        files = cursor_assistant.list_files()[:5]
        context = f"Project files: {files}"
        
        ai_response = cursor_assistant.get_ai_response(message, context)
        
        return f"""
## 🤖 AI Assistant Response

{ai_response}

---

### 💡 **What I can help you with:**

📊 **Mixpanel Analytics:**
- User activity analysis
- Event tracking insights
- Data visualization

🤖 **Development Support:**
- Code analysis & debugging
- File operations
- Search & navigation

Try asking me:
- "Show me activity for user [ID]"
- "Read [filename]"
- "Search for [pattern]"
- "What are the top events?"
- "Help me debug this code"

Or use the Quick Actions buttons below!
        """
    else:
        return f"""
I understand you're asking: "{message}"

I'm here to help with both Mixpanel data analysis and development tasks!

## 🚀 **Available Features:**

### 📊 **Mixpanel Data Analysis:**
- User activity tracking
- Event analysis and trends
- Data insights and summaries

### 🤖 **Cursor-like Development Help:**
- File reading and navigation
- Code search and analysis
- Development assistance

### 💬 **Try These Commands:**
- "Show me activity for user [ID]"
- "List files in the project"
- "Read [filename]"
- "Search for [code pattern]"
- "What are the top events?"

**💡 Tip:** Add your OpenAI API key to get even smarter AI responses!

Use the Quick Actions buttons below for common tasks!
        """

if __name__ == "__main__":
    main() 