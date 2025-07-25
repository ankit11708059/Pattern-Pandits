import streamlit as st
import os
import json
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import httpx
from typing import List, Dict, Optional, Any
import plotly.express as px
import plotly.graph_objects as go

# Load environment variables
load_dotenv()

# Network security setup
from network_utils import install_insecure_ssl
install_insecure_ssl()

# LangChain and AI imports
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.memory import ConversationBufferWindowMemory

# Import from existing modules
from rag_utils import search_analytics_knowledge, get_exact_analytics_event

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
ANALYTICS_KNOWLEDGE_INDEX = "analytics-events-knowledge-base-512"
DIMENSIONS = 512

class EnhancedAnalyticsChatAssistant:
    def __init__(self):
        """Initialize the Enhanced Analytics Chat Assistant"""
        self.setup_connections()
        self.setup_llm()
        self.setup_memory()
        self.setup_session_state()
        self.load_system_prompt()
    
    def setup_connections(self):
        """Setup Pinecone and OpenAI connections"""
        try:
            # Initialize Pinecone
            self.pc = Pinecone(api_key=PINECONE_API_KEY, ssl_verify=False) if PINECONE_API_KEY else None
            self.analytics_index = None
            
            if self.pc:
                try:
                    self.analytics_index = self.pc.Index(ANALYTICS_KNOWLEDGE_INDEX)
                    st.success(f"✅ Connected to analytics knowledge base: {ANALYTICS_KNOWLEDGE_INDEX}")
                except Exception as e:
                    st.error(f"❌ Failed to connect to analytics index: {e}")
            
            # Initialize OpenAI Embeddings
            self.embeddings = OpenAIEmbeddings(
                api_key=OPENAI_API_KEY,
                model="text-embedding-3-small",
                dimensions=DIMENSIONS,
                http_client=httpx.Client(verify=False, timeout=30),
            ) if OPENAI_API_KEY else None
            
            # Initialize Vector Store
            self.vector_store = PineconeVectorStore(
                index=self.analytics_index, 
                embedding=self.embeddings
            ) if self.analytics_index and self.embeddings else None
            
        except Exception as e:
            st.error(f"❌ Connection setup error: {e}")
            self.pc = None
            self.analytics_index = None
            self.embeddings = None
            self.vector_store = None
    
    def setup_llm(self):
        """Setup ChatOpenAI LLM with advanced configuration"""
        try:
            self.llm = ChatOpenAI(
                api_key=OPENAI_API_KEY,
                model="gpt-4o",
                temperature=0.1,
                max_tokens=3000,
                http_client=httpx.Client(verify=False, timeout=90)
            ) if OPENAI_API_KEY else None
            
            if self.llm:
                st.success("✅ ChatOpenAI (GPT-4o) initialized successfully")
            else:
                st.error("❌ OpenAI API key not configured")
                
        except Exception as e:
            st.error(f"❌ LLM setup error: {e}")
            self.llm = None
    
    def setup_memory(self):
        """Setup conversation memory"""
        self.memory = ConversationBufferWindowMemory(
            k=10,  # Remember last 10 exchanges
            return_messages=True
        ) if self.llm else None
    
    def setup_session_state(self):
        """Setup Streamlit session state for enhanced chat"""
        if 'enhanced_chat_messages' not in st.session_state:
            st.session_state.enhanced_chat_messages = []
        if 'analytics_insights' not in st.session_state:
            st.session_state.analytics_insights = {}
        if 'conversation_context' not in st.session_state:
            st.session_state.conversation_context = {}
        if 'favorite_events' not in st.session_state:
            st.session_state.favorite_events = []
        if 'chat_statistics' not in st.session_state:
            st.session_state.chat_statistics = {
                'total_queries': 0,
                'events_explored': set(),
                'topics_discussed': set()
            }
    
    def load_system_prompt(self):
        """Load comprehensive system prompt for analytics expertise"""
        self.system_prompt = """
You are an elite Senior Analytics Consultant and Mixpanel expert specializing in mobile app user behavior analytics. You have deep expertise in:

🎯 **CORE COMPETENCIES:**
- Mobile app analytics and user journey optimization
- Mixpanel event tracking and funnel analysis
- Conversion rate optimization and A/B testing
- User behavior patterns and segmentation
- iOS vs Android platform differences
- SIM binding, authentication, and financial app flows
- KYC processes, VCIP, and regulatory compliance
- UPI payments, banking flows, and fintech analytics

📊 **ANALYTICAL APPROACH:**
- Always provide data-driven insights with specific metrics
- Explain the "why" behind user behaviors, not just the "what"
- Connect individual events to broader user journey narratives
- Identify optimization opportunities with estimated impact
- Consider business context and revenue implications

🧠 **COMMUNICATION STYLE:**
- Expert-level insights delivered in clear, actionable language
- Use specific examples and real scenarios
- Provide step-by-step analysis for complex topics
- Always include practical recommendations
- Reference specific events from the knowledge base

🔍 **SPECIALIZATIONS:**
- Authentication flows (MPIN, biometric, SIM binding)
- Onboarding optimization and user acquisition
- Payment funnel analysis and drop-off reduction
- Mobile-first user experience optimization
- Regulatory compliance analytics (KYC, VCIP)
- Cross-platform behavior analysis
- Error tracking and debugging methodologies

Remember: You're helping product teams, developers, and business stakeholders make data-driven decisions that directly impact user experience and business outcomes.
"""
    
    def search_enhanced_analytics(self, query: str, k: int = 8) -> List[Dict]:
        """Enhanced analytics search with better context and scoring"""
        try:
            # Use the existing rag_utils function for consistency
            results = search_analytics_knowledge(query, k=k)
            
            # Enhance results with additional context
            enhanced_results = []
            for result in results:
                enhanced_result = result.copy()
                
                # Add category classification
                event_name = result.get('event_name', '').lower()
                enhanced_result['category'] = self.classify_event_category(event_name)
                
                # Add importance score based on query context
                enhanced_result['importance'] = self.calculate_importance_score(result, query)
                
                enhanced_results.append(enhanced_result)
            
            # Sort by importance and relevance
            enhanced_results.sort(key=lambda x: (x.get('importance', 0), x.get('score', 0)), reverse=True)
            
            return enhanced_results
            
        except Exception as e:
            st.error(f"❌ Enhanced analytics search error: {e}")
            return []
    
    def classify_event_category(self, event_name: str) -> str:
        """Classify events into categories for better organization"""
        categories = {
            'authentication': ['login', 'mpin', 'biometric', 'otp', 'verification'],
            'onboarding': ['onboard', 'signup', 'registration', 'welcome', 'intro'],
            'payment': ['payment', 'upi', 'transaction', 'wallet', 'banking'],
            'navigation': ['screen', 'page', 'navigation', 'tab', 'menu'],
            'engagement': ['clicked', 'viewed', 'shared', 'liked', 'scroll'],
            'compliance': ['kyc', 'vcip', 'ckyc', 'verification', 'document'],
            'error': ['error', 'failed', 'timeout', 'exception'],
            'lifecycle': ['app_open', 'app_closed', 'session', 'install']
        }
        
        for category, keywords in categories.items():
            if any(keyword in event_name for keyword in keywords):
                return category
        
        return 'other'
    
    def calculate_importance_score(self, result: Dict, query: str) -> float:
        """Calculate importance score based on various factors"""
        base_score = result.get('score', 0)
        
        # Boost score for exact matches
        if query.lower() in result.get('event_name', '').lower():
            base_score *= 1.5
        
        # Boost score for complete descriptions
        if len(result.get('description', '')) > 100:
            base_score *= 1.2
        
        return base_score
    
    def generate_enhanced_response(self, user_question: str) -> Dict[str, Any]:
        """Generate enhanced response with analytics insights and visualizations"""
        try:
            if not self.llm:
                return {"content": "❌ LLM not available. Please configure OpenAI API key.", "type": "error"}
            
            # Update statistics
            st.session_state.chat_statistics['total_queries'] += 1
            
            # Step 1: Enhanced analytics search
            analytics_results = self.search_enhanced_analytics(user_question, k=10)
            
            # Step 2: Extract key insights
            insights = self.extract_key_insights(analytics_results, user_question)
            
            # Step 3: Build comprehensive context
            analytics_context = self.build_analytics_context(analytics_results, insights)
            
            # Step 4: Create conversation history context
            conversation_context = self.get_conversation_context()
            
            # Step 5: Generate response with system prompt
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=f"""
**CURRENT QUESTION:** {user_question}

**ANALYTICS KNOWLEDGE CONTEXT:**
{analytics_context}

**CONVERSATION HISTORY:**
{conversation_context}

**EXTRACTED INSIGHTS:**
{json.dumps(insights, indent=2)}

Please provide a comprehensive, expert-level response that:
1. Directly answers the user's question
2. Uses specific analytics knowledge from the context
3. Provides actionable insights and recommendations
4. Connects to broader user journey and business impact
5. Includes specific metrics or examples when relevant
""")
            ]
            
            response = self.llm.invoke(messages)
            
            # Step 6: Update conversation memory
            if self.memory:
                self.memory.save_context(
                    {"input": user_question},
                    {"output": response.content}
                )
            
            # Step 7: Update analytics insights for session
            self.update_session_insights(analytics_results, user_question)
            
            return {
                "content": response.content,
                "type": "success",
                "analytics_used": len(analytics_results),
                "categories": list(set([r.get('category', 'other') for r in analytics_results])),
                "insights": insights,
                "sources": analytics_results[:3]  # Top 3 sources
            }
            
        except Exception as e:
            return {
                "content": f"❌ Error generating response: {e}",
                "type": "error"
            }
    
    def extract_key_insights(self, analytics_results: List[Dict], query: str) -> Dict[str, Any]:
        """Extract key insights from analytics results"""
        insights = {
            "total_events_found": len(analytics_results),
            "categories_involved": [],
            "key_user_actions": [],
            "potential_issues": [],
            "optimization_opportunities": []
        }
        
        for result in analytics_results:
            category = result.get('category', 'other')
            if category not in insights["categories_involved"]:
                insights["categories_involved"].append(category)
            
            event_name = result.get('event_name', '')
            if event_name:
                insights["key_user_actions"].append(event_name)
            
            # Identify potential issues
            if 'error' in event_name.lower() or 'failed' in result.get('description', '').lower():
                insights["potential_issues"].append(event_name)
        
        return insights
    
    def build_analytics_context(self, analytics_results: List[Dict], insights: Dict) -> str:
        """Build comprehensive analytics context for the LLM"""
        context = f"📊 **ANALYTICS KNOWLEDGE BASE RESULTS** (Found {len(analytics_results)} relevant events)\n\n"
        
        # Group by category
        by_category = {}
        for result in analytics_results[:8]:  # Top 8 results
            category = result.get('category', 'other')
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(result)
        
        for category, results in by_category.items():
            context += f"**{category.upper()} EVENTS:**\n"
            for result in results:
                event_name = result.get('event_name', 'Unknown')
                description = result.get('description', '')[:150]
                score = result.get('score', 0)
                context += f"• {event_name} (relevance: {score:.3f})\n"
                context += f"  {description}{'...' if len(result.get('description', '')) > 150 else ''}\n\n"
        
        return context
    
    def get_conversation_context(self) -> str:
        """Get relevant conversation context"""
        if not st.session_state.enhanced_chat_messages:
            return "This is the start of our conversation."
        
        # Get last 4 exchanges for context
        recent_messages = st.session_state.enhanced_chat_messages[-8:]
        context = "RECENT CONVERSATION:\n"
        
        for msg in recent_messages:
            role = "Human" if msg["role"] == "user" else "Assistant"
            content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
            context += f"{role}: {content}\n"
        
        return context
    
    def update_session_insights(self, analytics_results: List[Dict], query: str):
        """Update session-level insights and statistics"""
        for result in analytics_results:
            event_name = result.get('event_name', '')
            if event_name:
                st.session_state.chat_statistics['events_explored'].add(event_name)
        
        # Extract topics from query
        topic_keywords = ['authentication', 'payment', 'onboarding', 'error', 'conversion', 'funnel']
        for keyword in topic_keywords:
            if keyword.lower() in query.lower():
                st.session_state.chat_statistics['topics_discussed'].add(keyword)
    
    def render_enhanced_interface(self):
        """Render the enhanced chat interface with analytics insights"""
        st.title("🚀 Enhanced Analytics Chat Assistant")
        st.markdown("**Powered by GPT-4o + Analytics Events Knowledge Base + Conversation Memory**")
        
        # Enhanced status dashboard
        self.render_status_dashboard()
        
        # Main chat area with analytics insights
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 💬 Chat Interface")
            self.render_chat_messages()
            self.render_chat_input()
        
        with col2:
            st.markdown("### 📊 Session Insights")
            self.render_session_insights()
        
        # Enhanced sidebar
        self.render_enhanced_sidebar()
    
    def render_status_dashboard(self):
        """Render enhanced status dashboard"""
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            status = "🟢 Connected" if self.analytics_index else "🔴 Disconnected"
            st.metric("📊 Knowledge Base", status)
        with col2:
            status = "🟢 Ready" if self.llm else "🔴 Not configured"
            st.metric("🧠 GPT-4o", status)
        with col3:
            st.metric("💬 Messages", len(st.session_state.enhanced_chat_messages))
        with col4:
            events_explored = len(st.session_state.chat_statistics['events_explored'])
            st.metric("🔍 Events Explored", events_explored)
        
        st.markdown("---")
    
    def render_chat_messages(self):
        """Render enhanced chat messages with analytics context"""
        if not st.session_state.enhanced_chat_messages:
            st.markdown("""
            ### 👋 Welcome to the Enhanced Analytics Chat Assistant!
            
            **I'm your expert analytics consultant with access to 375+ event definitions and deep Mixpanel expertise.**
            
            **💡 Expert Areas:**
            - 🔐 Authentication flows (MPIN, SIM binding, biometric)
            - 🛣️ User journey optimization and funnel analysis  
            - 💳 Payment flows and financial app analytics
            - 📱 iOS vs Android behavioral differences
            - 🏦 KYC, VCIP, and compliance analytics
            - 🔧 Error debugging and performance optimization
            
            **🎯 Ask me complex questions like:**
            - "Analyze the complete MPIN authentication flow and identify optimization opportunities"
            - "What's the difference between iOS and Android user behavior in payment funnels?"
            - "How can we reduce drop-offs in the SIM binding process?"
            - "Explain the complete KYC journey and potential friction points"
            """)
        else:
            for message in st.session_state.enhanced_chat_messages:
                if message["role"] == "user":
                    with st.chat_message("user"):
                        st.write(message["content"])
                        st.caption(f"🕐 {message.get('timestamp', '')}")
                else:
                    with st.chat_message("assistant"):
                        st.write(message["content"])
                        
                        # Show analytics metadata
                        if "analytics_used" in message:
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.caption(f"📊 {message['analytics_used']} events analyzed")
                            with col2:
                                categories = message.get('categories', [])
                                st.caption(f"🏷️ {', '.join(categories)}")
                            with col3:
                                st.caption(f"🕐 {message.get('timestamp', '')}")
    
    def render_chat_input(self):
        """Render enhanced chat input with smart suggestions"""
        # Smart suggestions based on conversation
        if st.session_state.enhanced_chat_messages:
            st.markdown("**💡 Smart Suggestions:**")
            suggestions = self.generate_smart_suggestions()
            
            cols = st.columns(len(suggestions))
            for i, suggestion in enumerate(suggestions):
                with cols[i]:
                    if st.button(suggestion, key=f"suggestion_{i}"):
                        self.process_user_input(suggestion)
        
        # Main input
        user_input = st.chat_input("Ask me anything about analytics, user behavior, or specific events...")
        
        if user_input:
            self.process_user_input(user_input)
    
    def generate_smart_suggestions(self) -> List[str]:
        """Generate smart follow-up suggestions"""
        if not st.session_state.enhanced_chat_messages:
            return ["What is MPIN validation?", "Explain SIM binding", "Show payment flow"]
        
        # Get recent topics
        recent_topics = st.session_state.chat_statistics['topics_discussed']
        
        suggestions = []
        if 'authentication' in recent_topics:
            suggestions.append("Compare iOS vs Android auth")
        if 'payment' in recent_topics:
            suggestions.append("Optimize payment funnel")
        if 'error' in recent_topics:
            suggestions.append("Debug strategy")
        
        # Add general suggestions
        if len(suggestions) < 3:
            suggestions.extend(["User journey analysis", "Conversion optimization", "Event troubleshooting"])
        
        return suggestions[:3]
    
    def process_user_input(self, user_input: str):
        """Process user input and generate response"""
        # Add user message
        timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.enhanced_chat_messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": timestamp
        })
        
        # Generate enhanced response
        with st.spinner("🧠 Analyzing with GPT-4o + Analytics Knowledge Base + Conversation Context..."):
            response_data = self.generate_enhanced_response(user_input)
        
        # Add assistant response with metadata
        response_message = {
            "role": "assistant",
            "content": response_data["content"],
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "type": response_data["type"]
        }
        
        # Add analytics metadata if successful
        if response_data["type"] == "success":
            response_message.update({
                "analytics_used": response_data["analytics_used"],
                "categories": response_data["categories"],
                "insights": response_data["insights"],
                "sources": response_data["sources"]
            })
        
        st.session_state.enhanced_chat_messages.append(response_message)
        
        # Rerun to show new messages
        st.rerun()
    
    def render_session_insights(self):
        """Render real-time session insights and analytics"""
        stats = st.session_state.chat_statistics
        
        # Session statistics
        st.metric("📋 Total Queries", stats['total_queries'])
        st.metric("🎯 Events Explored", len(stats['events_explored']))
        st.metric("📚 Topics Discussed", len(stats['topics_discussed']))
        
        # Recent events explored
        if stats['events_explored']:
            st.markdown("**🔍 Recent Events:**")
            recent_events = list(stats['events_explored'])[-5:]
            for event in recent_events:
                st.markdown(f"• `{event}`")
        
        # Topics covered
        if stats['topics_discussed']:
            st.markdown("**📖 Topics Covered:**")
            for topic in stats['topics_discussed']:
                st.badge(topic, color="blue")
    
    def render_enhanced_sidebar(self):
        """Render enhanced sidebar with advanced analytics tools"""
        with st.sidebar:
            st.header("🛠️ Advanced Analytics Tools")
            
            # Event explorer
            st.subheader("🔍 Event Explorer")
            event_name = st.text_input("Event name:", placeholder="e.g., mpin_validated")
            
            if st.button("🔍 Deep Dive") and event_name:
                self.explore_event_deep_dive(event_name)
            
            # Analytics insights
            st.subheader("📊 Quick Analytics")
            if st.button("📈 Show Event Categories"):
                self.show_event_categories()
            
            if st.button("🔄 Analyze User Flow"):
                self.analyze_user_flow()
            
            # Conversation management
            st.subheader("💬 Conversation")
            if st.button("📁 Export Chat"):
                self.export_conversation()
            
            if st.button("🗑️ Clear Chat"):
                st.session_state.enhanced_chat_messages = []
                st.session_state.chat_statistics = {
                    'total_queries': 0,
                    'events_explored': set(),
                    'topics_discussed': set()
                }
                if self.memory:
                    self.memory.clear()
                st.rerun()
    
    def explore_event_deep_dive(self, event_name: str):
        """Perform deep dive analysis of a specific event"""
        event_info = get_exact_analytics_event(event_name)
        if event_info:
            st.success("✅ Event found!")
            st.json(event_info)
            
            # Add to conversation automatically
            deep_dive_question = f"Provide a comprehensive analysis of the '{event_name}' event including user context, business impact, and optimization opportunities"
            self.process_user_input(deep_dive_question)
        else:
            st.error("❌ Event not found")
    
    def show_event_categories(self):
        """Show analytics about event categories"""
        categories_question = "Show me a breakdown of event categories in the knowledge base and explain the key events in each category"
        self.process_user_input(categories_question)
    
    def analyze_user_flow(self):
        """Analyze typical user flows"""
        flow_question = "Analyze typical user flows in mobile financial apps, focusing on authentication, onboarding, and payment processes"
        self.process_user_input(flow_question)
    
    def export_conversation(self):
        """Export conversation to downloadable format"""
        conversation_data = {
            "timestamp": datetime.now().isoformat(),
            "messages": st.session_state.enhanced_chat_messages,
            "statistics": {
                "total_queries": st.session_state.chat_statistics['total_queries'],
                "events_explored": list(st.session_state.chat_statistics['events_explored']),
                "topics_discussed": list(st.session_state.chat_statistics['topics_discussed'])
            }
        }
        
        json_str = json.dumps(conversation_data, indent=2)
        st.download_button(
            label="📥 Download Conversation",
            data=json_str,
            file_name=f"analytics_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

def main():
    """Main application entry point"""
    st.set_page_config(
        page_title="Enhanced Analytics Chat Assistant",
        page_icon="🚀",
        layout="wide"
    )
    
    # Custom CSS for enhanced UI
    st.markdown("""
    <style>
    .stApp > header {
        background-color: transparent;
    }
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .main .block-container {
        background-color: rgba(255, 255, 255, 0.95);
        border-radius: 10px;
        padding: 2rem;
        margin-top: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize assistant
    assistant = EnhancedAnalyticsChatAssistant()
    
    # Render interface
    assistant.render_enhanced_interface()

if __name__ == "__main__":
    main() 