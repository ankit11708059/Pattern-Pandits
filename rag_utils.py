import os, json, httpx
import pandas as pd
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Disable SSL verification before importing any network libraries
from network_utils import install_insecure_ssl
install_insecure_ssl()

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from langchain_core.prompts import PromptTemplate

DIMENSIONS = 512
EVENT_CATALOG_INDEX = "event-catalog"
FAQ_INDEX = "faq"
ANALYTICS_KNOWLEDGE_INDEX = "analytics-event-knowledge"

# Embedding + Pinecone clients (singleton)
_OPENAI_KEY = os.getenv("OPENAI_API_KEY")
_PINECONE_KEY = os.getenv("PINECONE_API_KEY")

try:
    _pc = Pinecone(api_key=_PINECONE_KEY, ssl_verify=False) if _PINECONE_KEY else None
    _event_index = _pc.Index(EVENT_CATALOG_INDEX) if _pc else None
    _faq_index = _pc.Index(FAQ_INDEX) if _pc else None
    _analytics_index = _pc.Index(ANALYTICS_KNOWLEDGE_INDEX) if _pc else None
except Exception as e:
    print(f"Warning: Pinecone initialization error: {e}")
    _pc = None
    _event_index = None
    _faq_index = None
    _analytics_index = None

try:
    _emb_model = (
        OpenAIEmbeddings(
            api_key=_OPENAI_KEY,
            model="text-embedding-3-small",
            dimensions=DIMENSIONS,
            http_client=httpx.Client(verify=False, timeout=30),
        )
        if _OPENAI_KEY
        else None
    )
except Exception as e:
    print(f"Warning: OpenAI embeddings initialization error: {e}")
    _emb_model = None

try:
    _event_catalog_vs = (
        PineconeVectorStore(index=_event_index, embedding=_emb_model) if _event_index and _emb_model else None
    )
    _faq_vs = (
        PineconeVectorStore(index=_faq_index, embedding=_emb_model) if _faq_index and _emb_model else None
    )
    _analytics_vs = (
        PineconeVectorStore(index=_analytics_index, embedding=_emb_model) if _analytics_index and _emb_model else None
    )
except Exception as e:
    print(f"Warning: PineconeVectorStore initialization error: {e}")
    _event_catalog_vs = None
    _faq_vs = None
    _analytics_vs = None


def get_exact_event_description(event_name: str) -> str:
    """
    Get EXACT event description from Pinecone vector database using event name as ID
    This ensures precise mapping from Mixpanel events to catalog descriptions
    """
    if not _event_index or not event_name:
        return f"Event catalog not available for {event_name}"
    
    try:
        # Method 1: Direct ID lookup in Pinecone index
        print(f"🔍 Looking up exact event: {event_name}")
        
        # Query Pinecone by exact ID match
        query_result = _event_index.query(
            vector=[0.0] * DIMENSIONS,  # Dummy vector for ID-based lookup
            filter={"event_name": {"$eq": event_name}},  # Exact ID match
            top_k=1,
            include_metadata=True
        )
        
        if query_result.matches and len(query_result.matches) > 0:
            match = query_result.matches[0]
            if match.metadata and 'description' in match.metadata:
                description = match.metadata['description']
                print(f"✅ Found exact match for {event_name}")
                return description
        
        # Method 2: Try semantic search as fallback
        print(f"🔍 Trying semantic search for: {event_name}")
        results = search_similar_events(event_name, k=1)
        if results and len(results) > 0:
            # Check if it's a close match
            if results[0]['event_name'].lower() == event_name.lower():
                print(f"✅ Found semantic match for {event_name}")
                return results[0]['description']
        
        # Method 3: Generate description from event name
        print(f"🔧 Generating description for: {event_name}")
        return generate_description_from_event_name(event_name)
        
    except Exception as e:
        print(f"❌ Error getting exact event description for {event_name}: {e}")
        return generate_description_from_event_name(event_name)


def search_faq(query: str, k: int = 3) -> list:
    """
    Search FAQ database for relevant question-answer pairs
    """
    if not _faq_vs:
        return []
    
    try:
        print(f"🔍 Searching FAQ for: {query}")
        results = _faq_vs.similarity_search(query, k=k)
        
        faq_results = []
        for result in results:
            faq_data = {
                'content': result.page_content,
                'question': result.metadata.get('question', ''),
                'answer': result.metadata.get('answer', ''),
                'type': result.metadata.get('type', 'faq'),
                'source': result.metadata.get('source', 'FAQ.txt')
            }
            faq_results.append(faq_data)
            print(f"✅ Found FAQ: {faq_data['question'][:50]}...")
        
        return faq_results
        
    except Exception as e:
        print(f"❌ Error searching FAQ: {e}")
        return []


def search_combined_knowledge(query: str, k_events: int = 3, k_faq: int = 2) -> dict:
    """
    Search both event catalog and FAQ databases for comprehensive results
    """
    results = {
        'events': [],
        'faq': [],
        'total_results': 0
    }
    
    # Search event catalog
    try:
        event_results = search_similar_events(query, k=k_events)
        if event_results:
            results['events'] = event_results
            print(f"✅ Found {len(event_results)} event results")
    except Exception as e:
        print(f"❌ Error searching events: {e}")
    
    # Search FAQ
    try:
        faq_results = search_faq(query, k=k_faq)
        if faq_results:
            results['faq'] = faq_results
            print(f"✅ Found {len(faq_results)} FAQ results")
    except Exception as e:
        print(f"❌ Error searching FAQ: {e}")
    
    results['total_results'] = len(results['events']) + len(results['faq'])
    print(f"📊 Total combined results: {results['total_results']}")
    
    return results


def enrich_with_event_desc(df: pd.DataFrame) -> pd.DataFrame:
    """Add event_desc column using exact ID lookup, then generate description from event name if not found."""
    if _event_catalog_vs is None or _event_index is None:
        df["event_desc"] = "Event catalog not available"
        return df
    
    unique_events = df["event"].unique().tolist()
    mapping = {}
    
    try:
        for event in unique_events:
            try:
                # Step 1: Try exact ID lookup in Pinecone
                fetch_response = _event_index.fetch(ids=[event])
                
                if hasattr(fetch_response, 'vectors') and fetch_response.vectors and event in fetch_response.vectors:
                    vector_data = fetch_response.vectors[event]
                    if hasattr(vector_data, 'metadata') and vector_data.metadata:
                        description = vector_data.metadata.get('description', '')
                        if description:
                            mapping[event] = description
                            print(f"✅ Found exact ID match for '{event}': {description[:100]}...")
                            continue
                
                # Step 2: If exact ID not found, generate description from event name
                generated_desc = generate_description_from_event_name(event)
                mapping[event] = generated_desc
                print(f"ℹ️ Generated description for '{event}': {generated_desc[:100]}...")
                
            except Exception as e:
                print(f"Error looking up event '{event}': {e}")
                # Fallback to generated description
                mapping[event] = generate_description_from_event_name(event)
                
    except Exception as e:
        print(f"Error in event enrichment: {e}")
        # Fallback to generated descriptions for all events
        mapping = {evt: generate_description_from_event_name(evt) for evt in unique_events}
    
    df["event_desc"] = df["event"].map(mapping)
    return df


def generate_description_from_event_name(event_name: str) -> str:
    """Generate a meaningful description from the event name itself"""
    if not event_name:
        return "Unknown event"
    
    # Clean up the event name
    cleaned_name = event_name.replace('_', ' ').replace('-', ' ').strip()
    
    # Common patterns and their meanings
    patterns = {
        'cta_clicked': 'call-to-action button clicked',
        'page_opened': 'page opened/viewed',
        'page_open': 'page opened/viewed', 
        'bottomsheet_opened': 'bottom sheet modal opened',
        'button_clicked': 'button clicked',
        'successful': 'completed successfully',
        'complete': 'completed',
        'completed': 'completed',
        'started': 'initiated/started',
        'failed': 'failed/encountered error',
        'error': 'error occurred',
        'land': 'user landed on page/screen',
        'view': 'viewed/displayed',
        'open': 'opened/launched',
        'close': 'closed/dismissed',
        'submit': 'submitted/sent',
        'cancel': 'cancelled/dismissed',
        'login': 'user authentication/login',
        'logout': 'user logged out',
        'signup': 'user registration/signup',
        'purchase': 'purchase/transaction',
        'payment': 'payment processing',
        'add_to_cart': 'item added to shopping cart',
        'checkout': 'checkout process',
        'search': 'search functionality',
        'filter': 'content filtering',
        'share': 'content sharing',
        'download': 'file/content download',
        'upload': 'file/content upload',
        'app_open': 'application opened/launched',
        'app_close': 'application closed',
        'notification': 'notification related',
        'settings': 'settings/preferences',
        'profile': 'user profile related',
        'onboard': 'onboarding process',
        'verify': 'verification process',
        'confirm': 'confirmation action',
        'retry': 'retry attempt',
        'refresh': 'content refresh',
        'scroll': 'content scrolling',
        'swipe': 'swipe gesture',
        'tap': 'tap/touch interaction',
        'banking': 'banking functionality',
        'upgrade': 'upgrade/enhancement action',
        'vcip': 'video customer identification process',
        'op': 'operation/process',
        'aa': 'account aggregation',
        'vpa': 'virtual payment address',
        'upi': 'unified payments interface',
        'kyc': 'know your customer verification',
        'otp': 'one-time password',
        'pin': 'personal identification number',
        'biometric': 'biometric authentication'
    }
    
    # Generate description based on patterns
    description_parts = []
    event_lower = cleaned_name.lower()
    
    # Check for specific patterns
    for pattern, meaning in patterns.items():
        if pattern in event_lower:
            if pattern not in ['land', 'view', 'open']:  # These are more generic
                description_parts.append(meaning)
                break
    
    # If no specific pattern found, create a generic description
    if not description_parts:
        # Handle common prefixes
        if event_lower.startswith('op_'):
            description_parts.append('operation or onboarding process')
        elif event_lower.startswith('aa_'):
            description_parts.append('account aggregation feature')
        elif event_lower.startswith('app_'):
            description_parts.append('application-level event')
        elif event_lower.startswith('user_'):
            description_parts.append('user interaction event')
        elif event_lower.startswith('page_'):
            description_parts.append('page-related event')
        elif '_cta' in event_lower:
            description_parts.append('call-to-action interaction')
        elif 'click' in event_lower:
            description_parts.append('click/tap interaction')
        elif 'land' in event_lower:
            description_parts.append('page landing/navigation event')
        elif 'open' in event_lower:
            description_parts.append('opening/viewing event')
        else:
            description_parts.append('user interaction or system event')
    
    # Create the final description
    if description_parts:
        base_description = description_parts[0]
    else:
        base_description = 'user interaction event'
    
    # Add context about the event
    final_description = f"Event '{event_name}' - {base_description.capitalize()}. "
    
    # Add interpretation of the event name structure
    if '_' in event_name:
        parts = event_name.split('_')
        if len(parts) >= 2:
            final_description += f"This appears to be a '{parts[-1]}' action related to '{' '.join(parts[:-1]).replace('_', ' ')}'."
    else:
        final_description += f"This appears to be related to {cleaned_name}."
    
    return final_description


_PROMPT = PromptTemplate(
    input_variables=["events_json", "catalog_json", "timeframe", "total_events"],
    template="""
You are a senior UX researcher and product analytics expert specializing in detailed user journey mapping and mobile app behavior analysis.

**ANALYSIS CONTEXT:**
- Time Period: {timeframe}
- Total Events Analyzed: {total_events}
- User Activity Data: Complete chronological user session
- Event Catalog: Detailed event descriptions and implementation context

**COMPLETE USER ACTIVITY DATA ({total_events} EVENTS):**
{events_json}

**EVENT CATALOG (Descriptions & Context):**
{catalog_json}

**MISSION: CREATE A DETAILED USER JOURNEY WALKTHROUGH**

Your goal is to create a comprehensive, chronological analysis that allows someone to visualize and understand exactly how the user navigated through the app during these {total_events} events. Think of this as creating a "movie script" of the user's journey.

**ANALYSIS STRUCTURE:**

• **Journey Overview:** Start with high-level summary of the complete {total_events} event session - timeframe, platform, key activities, and overall user intent

• **Session Phases:** Break the journey into 4-6 logical phases based on user behavior patterns and app sections visited

• **Detailed Navigation Flow:** For each phase, provide chronological walkthrough of user actions:
  ◦ What screen/section they entered
  ◦ What actions they performed
  ◦ How they moved between features
  ◦ What this reveals about their intent
  ◦ Any friction points or smooth transitions

• **Key User Decisions:** Highlight critical moments where user made important choices or encountered decision points

• **App Feature Usage:** Document which features/screens were most used and how user interacted with them

• **User Intent Evolution:** Show how user's goals and focus changed throughout the session

• **Technical Context:** Use event catalog to explain what each action technically represents and why it matters

• **UX Assessment:** Identify smooth user flows vs friction points based on event sequences and timing

**DETAILED REQUIREMENTS:**

1. **CHRONOLOGICAL FLOW:** Present events in time order so reader can follow the user's exact path
2. **COMPREHENSIVE COVERAGE:** Include insights about ALL major event types and user actions
3. **VISUAL STORYTELLING:** Use descriptive language that helps reader visualize the user's experience
4. **CONTEXTUAL EXPLANATIONS:** For each major action, explain what it means in terms of app functionality
5. **PATTERN RECOGNITION:** Identify and explain repeated behaviors, loops, or user habits
6. **ACTIONABLE INSIGHTS:** Provide specific observations about user experience quality

**EXAMPLE DETAILED ANALYSIS STYLE:**

• **Journey Overview:** User embarked on an intensive 369-event session spanning 70 minutes on Android, demonstrating high engagement with banking and onboarding features, ultimately completing a full financial services registration flow

• **Phase 1 - App Entry & Initial Exploration (Events 1-50):**
  ◦ Session began with app_open at [time], indicating fresh app launch or return from background
  ◦ User immediately engaged with navigation elements (nav_bar_clicked, nav_bar_swiped), showing exploratory behavior
  ◦ Quick progression to rewards section (rewards_homescreen_open) suggests familiarity with app layout
  ◦ Multiple sync events (app_sync_started, location_sync_started) indicate app performing background data updates

• **Phase 2 - Banking Feature Discovery (Events 51-120):**
  ◦ User discovered borrowing features (borrow_page_opened, borrow_details_page_opened), spending significant time exploring loan options
  ◦ Engagement with borrow_slider_swiped and borrow_details_info_clicked shows active interest in loan parameters
  ◦ Multiple leaderboard interactions (leaderboard_page_opened, leaderboard_card_clicked) suggest gamification engagement

• **Phase 3 - Onboarding Process (Events 121-250):**
  ◦ Critical transition to onboarding with op_land events, marking beginning of account creation process
  ◦ User progressed through verification steps (op_vcip_land for video KYC, mpin_verify_screen for security setup)
  ◦ Multiple op_cta_action events show user actively responding to call-to-action prompts throughout onboarding

• **Phase 4 - Help & Support Engagement (Events 251-350):**
  ◦ Extensive help system usage (help_home_screen, help_query_screen, help_chat_cta_clicked) indicates user needed assistance
  ◦ Chatbot interaction sequence (chatbot_open, chatbot_option_clicked, chatbot_first_screen_options_shown) shows proactive help-seeking
  ◦ Help category exploration (help_category_clicked, help_faq_category_screen) suggests user researching specific issues

• **Session Conclusion (Events 351-369):**
  ◦ Final events show session_timeout and app_closed, indicating natural session conclusion
  ◦ No abrupt abandonment - user completed their intended journey

**CRITICAL:** Ensure your analysis covers ALL significant user actions and provides enough detail that someone reading it can mentally "walk through" the user's complete app experience step by step. Include specific event names and explain what each major action means for the user experience.
""",
)


def summarize_session(df: pd.DataFrame) -> str:
    """Enhanced comprehensive session summary covering ALL events in the timeframe"""
    if _OPENAI_KEY is None:
        return "(OpenAI key missing — cannot generate summary)"
    
    if _event_catalog_vs is None or _event_index is None:
        return "(Pattern Pandits event catalog not available — using basic summary)"
    
    try:
        # Ensure we process ALL events, not just a subset
        total_events = len(df)
        
        if total_events == 0:
            return "No events found in the selected timeframe."
        
        print(f"Processing comprehensive analysis for {total_events} events...")
        
        # Get comprehensive event context from Pattern Pandits catalog
        unique_events = df['event'].unique().tolist()
        comprehensive_catalog = {}
        
        # Get detailed descriptions for all unique events in the session (limit to essential info)
        print(f"Enriching {len(unique_events)} unique event types...")
        for event in unique_events:
            similar_events = search_similar_events(event, k=1)
            if similar_events:
                # Truncate descriptions to save tokens
                description = similar_events[0]["description"][:80] + "..." if len(similar_events[0]["description"]) > 80 else similar_events[0]["description"]
                comprehensive_catalog[event] = {
                    "description": description,
                    "relevance": similar_events[0]["relevance"]
                }
            else:
                comprehensive_catalog[event] = {
                    "description": f"Event: {event}",
                    "relevance": "Unknown"
                }
        
        # Calculate comprehensive timeframe
        if not df.empty and pd.notna(df["time"]).any():
            start_time = df["time"].min().strftime("%Y-%m-%d %H:%M:%S")
            end_time = df["time"].max().strftime("%Y-%m-%d %H:%M:%S")
            duration = df["time"].max() - df["time"].min()
            timeframe = f"{start_time} to {end_time} (Duration: {duration})"
        else:
            timeframe = "Unknown timeframe"
        
        # Smart token-aware data preparation
        if total_events <= 50:
            # Small dataset - include all events with full details
            events_with_context = []
            for index, row in df.iterrows():
                event_info = {
                    "seq": index + 1,
                    "time": row["time"].strftime("%H:%M:%S") if pd.notna(row["time"]) else "Unknown",
                    "event": row["event"],
                    "description": comprehensive_catalog.get(row["event"], {}).get("description", "")[:60],
                    "platform": row.get("platform", "Unknown"),
                    "location": f"{row.get('city', 'Unknown')}, {row.get('country', 'Unknown')}"
                }
                events_with_context.append(event_info)
            
            events_json = json.dumps(events_with_context, default=str)
            
        elif total_events <= 200:
            # Medium dataset - detailed chronological sampling
            events_with_context = []
            
            # Include first 20 events with descriptions
            for index in range(min(20, total_events)):
                row = df.iloc[index]
                events_with_context.append({
                    "seq": index + 1,
                    "time": row["time"].strftime("%H:%M:%S") if pd.notna(row["time"]) else "Unknown",
                    "event": row["event"],
                    "description": comprehensive_catalog.get(row["event"], {}).get("description", "")[:50],
                    "platform": row.get("platform", "Unknown")
                })
            
            # Include every 8th event from middle with context
            middle_start = 20
            middle_end = max(total_events - 20, middle_start)
            for index in range(middle_start, middle_end, 8):
                if index < total_events:
                    row = df.iloc[index]
                    events_with_context.append({
                        "seq": index + 1,
                        "time": row["time"].strftime("%H:%M:%S") if pd.notna(row["time"]) else "Unknown",
                        "event": row["event"],
                        "description": comprehensive_catalog.get(row["event"], {}).get("description", "")[:50],
                        "platform": row.get("platform", "Unknown")
                    })
            
            # Include last 20 events with descriptions
            for index in range(max(0, total_events - 20), total_events):
                row = df.iloc[index]
                events_with_context.append({
                    "seq": index + 1,
                    "time": row["time"].strftime("%H:%M:%S") if pd.notna(row["time"]) else "Unknown",
                    "event": row["event"],
                    "description": comprehensive_catalog.get(row["event"], {}).get("description", "")[:50],
                    "platform": row.get("platform", "Unknown")
                })
            
            events_json = json.dumps(events_with_context, default=str)
            
        else:
            # Large dataset - strategic comprehensive sampling for journey analysis
            # Get event frequency and timing statistics
            event_counts = df['event'].value_counts().to_dict()
            platform_counts = df['platform'].value_counts().to_dict() if 'platform' in df.columns else {}
            
            # Create chronological journey segments
            segment_size = total_events // 6  # Divide into 6 phases
            journey_segments = []
            
            for segment_num in range(6):
                start_idx = segment_num * segment_size
                end_idx = min((segment_num + 1) * segment_size, total_events)
                
                if start_idx < total_events:
                    # Sample events from this segment
                    segment_events = []
                    
                    # Always include first and last events of segment
                    if start_idx < end_idx:
                        first_row = df.iloc[start_idx]
                        segment_events.append({
                            "seq": start_idx + 1,
                            "time": first_row["time"].strftime("%H:%M:%S") if pd.notna(first_row["time"]) else "Unknown",
                            "event": first_row["event"],
                            "description": comprehensive_catalog.get(first_row["event"], {}).get("description", "")[:40],
                            "platform": first_row.get("platform", "Unknown"),
                            "segment": f"Phase_{segment_num + 1}"
                        })
                    
                    # Sample middle events of segment
                    for idx in range(start_idx + 1, end_idx - 1, max(1, (end_idx - start_idx) // 4)):
                        if idx < total_events:
                            row = df.iloc[idx]
                            segment_events.append({
                                "seq": idx + 1,
                                "time": row["time"].strftime("%H:%M:%S") if pd.notna(row["time"]) else "Unknown",
                                "event": row["event"],
                                "description": comprehensive_catalog.get(row["event"], {}).get("description", "")[:40],
                                "platform": row.get("platform", "Unknown"),
                                "segment": f"Phase_{segment_num + 1}"
                            })
                    
                    # Last event of segment
                    if end_idx > start_idx + 1 and end_idx - 1 < total_events:
                        last_row = df.iloc[end_idx - 1]
                        segment_events.append({
                            "seq": end_idx,
                            "time": last_row["time"].strftime("%H:%M:%S") if pd.notna(last_row["time"]) else "Unknown",
                            "event": last_row["event"],
                            "description": comprehensive_catalog.get(last_row["event"], {}).get("description", "")[:40],
                            "platform": last_row.get("platform", "Unknown"),
                            "segment": f"Phase_{segment_num + 1}"
                        })
                    
                    journey_segments.extend(segment_events)
            
            # Create comprehensive journey data
            journey_analysis = {
                "total_events": total_events,
                "session_duration": timeframe,
                "unique_event_types": len(unique_events),
                "top_events": dict(list(event_counts.items())[:8]),
                "platform_distribution": platform_counts,
                "chronological_journey": journey_segments,
                "journey_phases": 6,
                "analysis_note": f"Detailed journey analysis of all {total_events} events across 6 chronological phases with event descriptions for comprehensive user flow understanding"
            }
            
            events_json = json.dumps(journey_analysis, default=str)
        
        # Compress catalog data
        catalog_summary = {}
        for event, info in comprehensive_catalog.items():
            catalog_summary[event] = info["description"]
        
        catalog_json = json.dumps(catalog_summary, default=str)
        
        # Estimate tokens (rough estimation: 1 token ≈ 4 characters)
        estimated_tokens = (len(events_json) + len(catalog_json) + len(timeframe) + 2000) // 4  # 2000 for prompt overhead
        print(f"Estimated tokens: {estimated_tokens}, Event data: {len(events_json)} chars, Catalog: {len(catalog_json)} chars")
        
        # If still too large, use even more aggressive reduction
        if estimated_tokens > 14000:  # Leave buffer for response
            print("Data still too large, applying aggressive reduction...")
            
            # Ultra-compressed format
            event_types_summary = {}
            for event in unique_events:
                count = len(df[df['event'] == event])
                platforms = df[df['event'] == event]['platform'].value_counts().to_dict() if 'platform' in df.columns else {}
                event_types_summary[event] = {
                    "count": count,
                    "platforms": platforms,
                    "description": comprehensive_catalog.get(event, {}).get("description", "")[:50]
                }
            
            ultra_summary = {
                "total_events": total_events,
                "timeframe": timeframe,
                "event_analysis": event_types_summary,
                "first_events": [df.iloc[i]['event'] for i in range(min(5, total_events))],
                "last_events": [df.iloc[i]['event'] for i in range(max(0, total_events-5), total_events)]
            }
            
            events_json = json.dumps(ultra_summary, default=str)
            catalog_json = "{}"  # Skip catalog to save space
        
        # Use enhanced model for comprehensive analysis
        llm = ChatOpenAI(
            api_key=_OPENAI_KEY,
            temperature=0.1,
            model="gpt-3.5-turbo-16k",
            http_client=httpx.Client(verify=False, timeout=120),
        )
        
        chain = _PROMPT | llm
        
        print(f"Final data sizes - Events: {len(events_json)}, Catalog: {len(catalog_json)}, Est. tokens: {(len(events_json) + len(catalog_json) + 2000) // 4}")
        
        result = chain.invoke({
            "events_json": events_json,
            "catalog_json": catalog_json,
            "timeframe": timeframe,
            "total_events": total_events
        })
        
        # Clean up the response and format properly for bullet points
        summary_text = str(result.content) if hasattr(result, 'content') else str(result)
        
        # Clean up formatting issues
        summary_text = summary_text.replace('\\n', '\n')
        summary_text = summary_text.replace('\n\n\n', '\n\n')
        summary_text = summary_text.strip()
        
        # Ensure proper bullet point formatting
        if not summary_text.startswith('•'):
            lines = summary_text.split('\n')
            formatted_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('•') and not line.startswith('◦'):
                    if any(keyword in line.lower() for keyword in ['overview', 'analysis', 'insight', 'pattern', 'behavior']):
                        formatted_lines.append(f'• {line}')
                    else:
                        formatted_lines.append(line)
                else:
                    formatted_lines.append(line)
            summary_text = '\n'.join(formatted_lines)
        
        print(f"Generated comprehensive analysis: {len(summary_text)} characters")
        return summary_text
        
    except Exception as e:
        print(f"Error in comprehensive summary generation: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to detailed basic summary
        unique_events_list = df['event'].unique().tolist()
        return f"""• **Error Notice:** Could not generate comprehensive analysis due to: {str(e)[:100]}...
• **Session Overview:** Contains {len(df)} total events across {len(unique_events_list)} unique event types during the selected timeframe
• **Event Types Present:** {', '.join(unique_events_list[:10])}{'...' if len(unique_events_list) > 10 else ''}
• **Recommendation:** This session may be too large for detailed analysis. Try a smaller date range or fewer user IDs for more detailed insights."""


def get_enhanced_funnel_insights(funnel_events: list, funnel_data: dict) -> str:
    """
    Get enhanced funnel insights using Pattern Pandits event catalog
    
    Args:
        funnel_events: List of event names in the funnel
        funnel_data: Mixpanel funnel data with metrics
    
    Returns:
        Enhanced AI insights string with event catalog context
    """
    if _event_catalog_vs is None or _OPENAI_KEY is None:
        return "Event catalog or OpenAI not available for enhanced insights"
    
    try:
        # Get detailed descriptions for all funnel events
        enhanced_event_context = {}
        for event in funnel_events:
            # Search for similar events in our catalog using direct Pinecone query
            similar_events = search_similar_events(event, k=3)
            if similar_events:
                enhanced_event_context[event] = similar_events
        
        # Create enhanced prompt for funnel analysis
        funnel_prompt = PromptTemplate(
            input_variables=["funnel_data", "event_context", "funnel_events"],
            template="""
You are a senior product analytics consultant specializing in mobile app funnels and user behavior optimization.

FUNNEL EVENTS: {funnel_events}

DETAILED EVENT CONTEXT from Pattern Pandits Event Catalog:
{event_context}

FUNNEL PERFORMANCE DATA:
{funnel_data}

**ANALYSIS REQUIREMENTS:**

1. **EVENT-SPECIFIC INSIGHTS:** 
   - For each funnel step, explain what the event actually does based on the detailed descriptions
   - Identify potential UX friction points based on event implementation details
   - Highlight technical constraints that might impact conversions

2. **DROP-OFF ANALYSIS:**
   - Analyze conversion rates between each step
   - Identify the biggest drop-off points with specific recommendations
   - Explain why users might abandon at each step based on event context

3. **OPTIMIZATION RECOMMENDATIONS:**
   - Provide specific UX improvements for high drop-off events
   - Suggest A/B test ideas based on event trigger conditions
   - Recommend tracking improvements or additional events

4. **BUSINESS IMPACT:**
   - Estimate revenue impact of fixing major drop-off points
   - Prioritize recommendations by effort vs impact
   - Suggest success metrics to track improvements

5. **TECHNICAL INSIGHTS:**
   - Comment on event implementation quality based on descriptions
   - Identify potential tracking gaps in the funnel
   - Suggest additional events for better insights

Provide actionable, data-driven recommendations with specific next steps.
"""
        )
        
        llm = ChatOpenAI(
            api_key=_OPENAI_KEY,
            temperature=0,
            model="gpt-3.5-turbo-16k",
            http_client=httpx.Client(verify=False, timeout=30),
        )
        
        chain = funnel_prompt | llm
        
        response = chain.invoke({
            "funnel_events": json.dumps(funnel_events),
            "event_context": json.dumps(enhanced_event_context, indent=2),
            "funnel_data": json.dumps(funnel_data, default=str)[:8000]
        })
        
        return str(response.content) if hasattr(response, 'content') else str(response)
        
    except Exception as e:
        return f"Error generating enhanced insights: {e}"


def search_similar_events(query: str, k: int = 5) -> list:
    """
    Search for events in the Pattern Pandits catalog
    First tries exact ID lookup, then generates description from event name if not found
    
    Args:
        query: Search query (event name/ID)
        k: Number of events to return (ignored for exact lookup)
    
    Returns:
        List with single event if exact match found, or generated description
    """
    if _event_index is None or _emb_model is None:
        # Generate description even without Pinecone
        generated_desc = generate_description_from_event_name(query)
        return [{
            "event_name": query,
            "description": generated_desc,
            "relevance": "Generated from event name"
        }]
    
    try:
        # Step 1: Try exact ID lookup first
        try:
            fetch_response = _event_index.fetch(ids=[query])
            
            if hasattr(fetch_response, 'vectors') and fetch_response.vectors and query in fetch_response.vectors:
                vector_data = fetch_response.vectors[query]
                if hasattr(vector_data, 'metadata') and vector_data.metadata:
                    description = vector_data.metadata.get('description', '')
                    event_name = vector_data.metadata.get('event_name', query)
                    
                    if description:
                        print(f"✅ Found exact ID match for '{query}'")
                        return [{
                            "event_name": event_name,
                            "description": description,
                            "relevance": "Exact ID Match"
                        }]
        except Exception as e:
            print(f"Direct ID lookup failed for '{query}': {e}")
        
        # Step 2: If exact ID not found, generate description from event name
        generated_desc = generate_description_from_event_name(query)
        print(f"ℹ️ Generated description for '{query}'")
        return [{
            "event_name": query,
            "description": generated_desc,
            "relevance": "Generated from event name"
        }]
        
    except Exception as e:
        print(f"Error searching events for '{query}': {e}")
        # Fallback to generated description
        generated_desc = generate_description_from_event_name(query)
        return [{
            "event_name": query,
            "description": generated_desc,
            "relevance": "Generated fallback"
        }]


def get_event_recommendations(current_events: list) -> dict:
    """
    Get recommendations for additional events to track based on current funnel
    
    Args:
        current_events: List of current events in funnel
    
    Returns:
        Dictionary with recommended events and reasons
    """
    if _event_catalog_vs is None:
        return {"recommendations": [], "message": "Event catalog not available"}
    
    try:
        recommendations = {}
        
        # For each current event, find related events that might be missing
        for event in current_events:
            similar_events = search_similar_events(event, k=10)
            
            # Filter out current events and suggest complementary ones
            suggested = []
            for similar in similar_events:
                if similar["event_name"] not in current_events:
                    suggested.append({
                        "event": similar["event_name"],
                        "description": similar["description"][:200] + "...",
                        "reason": f"Commonly tracked alongside {event}"
                    })
            
            if suggested:
                recommendations[event] = suggested[:3]  # Top 3 suggestions per event
        
        return recommendations
        
    except Exception as e:
        return {"error": f"Error getting recommendations: {e}"} 


def search_analytics_knowledge(query: str, k: int = 5) -> list:
    """
    Search analytics knowledge base for event insights, patterns, and debugging info
    """
    if not _analytics_index or not _emb_model:
        return []
    
    try:
        print(f"🔍 Searching analytics knowledge for: {query}")
        
        # Create embedding for the query
        query_embedding = _emb_model.embed_query(query)
        
        # Search using Pinecone index directly
        query_result = _analytics_index.query(
            vector=query_embedding,
            top_k=k,
            include_metadata=True
        )
        
        analytics_results = []
        for match in query_result.matches:
            if match.metadata:
                analytics_data = {
                    'content': match.metadata.get('description', ''),
                    'event_name': match.metadata.get('event_name', ''),
                    'context': match.metadata.get('context', ''),
                    'timing': match.metadata.get('timing', ''),
                    'screen': match.metadata.get('screen', ''),
                    'debug_usage': match.metadata.get('debug_usage', ''),
                    'examples': match.metadata.get('examples', ''),
                    'user_journey': match.metadata.get('user_journey', ''),
                    'implementation': match.metadata.get('implementation', ''),
                    'properties': match.metadata.get('properties', ''),
                    'type': match.metadata.get('type', 'analytics_knowledge'),
                    'description': match.metadata.get('description', ''),
                    'full_content': match.metadata.get('full_content', ''),
                    'score': match.score
                }
                analytics_results.append(analytics_data)
                print(f"✅ Found analytics: {analytics_data['event_name'] or 'Knowledge'} (score: {match.score:.3f})")
        
        return analytics_results
        
    except Exception as e:
        print(f"❌ Error searching analytics knowledge: {e}")
        return []


def get_exact_analytics_event(event_name: str) -> dict:
    """
    Get exact analytics knowledge for a specific event name
    """
    if not _analytics_index or not event_name:
        return {}
    
    try:
        print(f"🔍 Looking up exact analytics for event: {event_name}")
        
        # Query by exact event name filter
        query_result = _analytics_index.query(
            vector=[0.0] * DIMENSIONS,  # Dummy vector for filter-based lookup
            filter={"event_name": {"$eq": event_name}},
            top_k=1,
            include_metadata=True
        )
        
        if query_result.matches and len(query_result.matches) > 0:
            match = query_result.matches[0]
            if match.metadata:
                print(f"✅ Found exact analytics match for {event_name}")
                return {
                    'event_name': match.metadata.get('event_name', event_name),
                    'description': match.metadata.get('description', ''),
                    'context': match.metadata.get('context', ''),
                    'timing': match.metadata.get('timing', ''),
                    'screen': match.metadata.get('screen', ''),
                    'debug_usage': match.metadata.get('debug_usage', ''),
                    'examples': match.metadata.get('examples', ''),
                    'user_journey': match.metadata.get('user_journey', ''),
                    'implementation': match.metadata.get('implementation', ''),
                    'properties': match.metadata.get('properties', ''),
                    'full_content': match.metadata.get('full_content', '')
                }
        
        # Fallback to similarity search
        print(f"🔍 Trying semantic search for: {event_name}")
        results = search_analytics_knowledge(event_name, k=1)
        if results and len(results) > 0:
            result = results[0]
            if result['event_name'].lower() == event_name.lower():
                print(f"✅ Found semantic analytics match for {event_name}")
                return result
        
        print(f"❌ No analytics knowledge found for {event_name}")
        return {}
        
    except Exception as e:
        print(f"❌ Error getting exact analytics for {event_name}: {e}")
        return {}


def search_combined_analytics_knowledge(query: str, k_analytics: int = 5, k_faq: int = 2) -> dict:
    """
    Search both analytics knowledge and FAQ databases for comprehensive results
    Prioritizes analytics knowledge over the old event catalog
    """
    results = {
        'analytics': [],
        'faq': [],
        'total_results': 0
    }
    
    # Search analytics knowledge (primary source)
    try:
        analytics_results = search_analytics_knowledge(query, k=k_analytics)
        if analytics_results:
            results['analytics'] = analytics_results
            print(f"✅ Found {len(analytics_results)} analytics results")
    except Exception as e:
        print(f"❌ Error searching analytics: {e}")
    
    # Search FAQ
    try:
        faq_results = search_faq(query, k=k_faq)
        if faq_results:
            results['faq'] = faq_results
            print(f"✅ Found {len(faq_results)} FAQ results")
    except Exception as e:
        print(f"❌ Error searching FAQ: {e}")
    
    results['total_results'] = len(results['analytics']) + len(results['faq'])
    print(f"📊 Total combined analytics results: {results['total_results']}")
    
    return results


def enrich_with_analytics_knowledge(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich Mixpanel data with analytics knowledge descriptions
    Uses the comprehensive analytics knowledge base instead of basic event catalog
    """
    if not _analytics_vs:
        df["event_desc"] = "Analytics knowledge not available"
        return df
    
    unique_events = df["event"].unique().tolist()
    mapping = {}
    
    try:
        for event in unique_events:
            try:
                # Get exact analytics knowledge for this event
                analytics_data = get_exact_analytics_event(event)
                
                if analytics_data and analytics_data.get('description'):
                    # Use the comprehensive description from analytics knowledge
                    description = analytics_data['description']
                    
                    # Add timing and context info if available
                    if analytics_data.get('timing'):
                        description += f" Timing: {analytics_data['timing']}"
                    
                    if analytics_data.get('context'):
                        description += f" Context: {analytics_data['context']}"
                    
                    mapping[event] = description
                    print(f"✅ Found analytics knowledge for '{event}': {description[:100]}...")
                else:
                    # Fallback to generated description
                    generated_desc = generate_description_from_event_name(event)
                    mapping[event] = generated_desc
                    print(f"ℹ️ Generated description for '{event}': {generated_desc[:100]}...")
                
            except Exception as e:
                print(f"Error looking up analytics for event '{event}': {e}")
                # Fallback to generated description
                mapping[event] = generate_description_from_event_name(event)
                
    except Exception as e:
        print(f"Error in analytics enrichment: {e}")
        # Fallback to generated descriptions for all events
        mapping = {evt: generate_description_from_event_name(evt) for evt in unique_events}
    
    df["event_desc"] = df["event"].map(mapping)
    return df 