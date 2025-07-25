import streamlit as st
import os
import json
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import httpx
from typing import List, Dict, Optional

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
from langchain_core.messages import HumanMessage, AIMessage

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
ANALYTICS_KNOWLEDGE_INDEX = "analytics-events-knowledge-base-512"
DIMENSIONS = 512

class AnalyticsChatAssistant:
    def __init__(self):
        """Initialize the Analytics Chat Assistant with LLM and Vector Database access"""
        self.setup_connections()
        self.setup_llm()
        self.setup_session_state()
    
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
        """Setup ChatOpenAI LLM"""
        try:
            self.llm = ChatOpenAI(
                api_key=OPENAI_API_KEY,
                model="gpt-4o",
                temperature=0.1,
                max_tokens=2000,
                http_client=httpx.Client(verify=False, timeout=60)
            ) if OPENAI_API_KEY else None
            
            if self.llm:
                st.success("✅ ChatOpenAI (GPT-4o) initialized successfully")
            else:
                st.error("❌ OpenAI API key not configured")
                
        except Exception as e:
            st.error(f"❌ LLM setup error: {e}")
            self.llm = None
    
    def setup_session_state(self):
        """Setup Streamlit session state for chat"""
        if 'chat_messages' not in st.session_state:
            st.session_state.chat_messages = []
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        if 'analytics_context' not in st.session_state:
            st.session_state.analytics_context = {}
    
    def search_analytics_knowledge(self, query: str, k: int = 5) -> List[Dict]:
        """Search the analytics knowledge base for relevant events"""
        try:
            if not self.vector_store:
                return []
            
            # Semantic search
            results = self.vector_store.similarity_search_with_score(query, k=k)
            
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'score': score,
                    'event_name': doc.metadata.get('event_name', 'Unknown'),
                    'description': doc.metadata.get('description', doc.page_content)
                })
            
            return formatted_results
            
        except Exception as e:
            st.error(f"❌ Analytics search error: {e}")
            return []
    
    def get_exact_event_info(self, event_name: str) -> Optional[Dict]:
        """Get exact information for a specific event"""
        try:
            if not self.analytics_index:
                return None
            
            # Try exact ID fetch first
            response = self.analytics_index.fetch(ids=[event_name])
            
            if response.vectors and event_name in response.vectors:
                vector_data = response.vectors[event_name]
                if vector_data.metadata:
                    return {
                        'event_name': event_name,
                        'description': vector_data.metadata.get('description', ''),
                        'context': vector_data.metadata.get('context', ''),
                        'timing': vector_data.metadata.get('timing', ''),
                        'screen': vector_data.metadata.get('screen', ''),
                        'debug_usage': vector_data.metadata.get('debug_usage', '')
                    }
            
            return None
            
        except Exception as e:
            print(f"❌ Exact event lookup error: {e}")
            return None
    
    def generate_enhanced_response(self, user_question: str) -> str:
        """Generate enhanced response using analytics knowledge + ChatOpenAI"""
        try:
            if not self.llm:
                return "❌ LLM not available. Please configure OpenAI API key."
            
            # Step 1: Search analytics knowledge base
            analytics_results = self.search_analytics_knowledge(user_question, k=8)
            
            # Step 2: Build context from analytics knowledge
            analytics_context = ""
            if analytics_results:
                analytics_context = "📊 **ANALYTICS EVENTS KNOWLEDGE BASE:**\n\n"
                for i, result in enumerate(analytics_results[:6], 1):
                    event_name = result['event_name']
                    description = result['description']
                    score = result['score']
                    
                    analytics_context += f"**{i}. {event_name}** (relevance: {score:.3f})\n"
                    analytics_context += f"   {description[:200]}{'...' if len(description) > 200 else ''}\n\n"
            
            # Step 3: Create comprehensive prompt
            prompt = PromptTemplate(
                input_variables=["question", "analytics_context", "chat_history"],
                template="""
You are an expert analytics consultant specializing in mobile app user behavior and Mixpanel events. You have access to a comprehensive analytics events knowledge base with 375+ detailed event descriptions.

**ANALYTICS KNOWLEDGE CONTEXT:**
{analytics_context}

**PREVIOUS CONVERSATION:**
{chat_history}

**USER QUESTION:**
{question}

**INSTRUCTIONS:**
- Provide detailed, expert-level insights about app analytics and user behavior
- Use the analytics knowledge base to explain events, user flows, and patterns
- If asked about specific events, provide comprehensive context including timing, screens, and business impact
- For debugging questions, provide step-by-step analysis and recommendations
- For optimization questions, suggest specific improvements with expected impact
- Keep explanations clear but comprehensive - you're talking to someone who understands analytics
- Reference specific events from the knowledge base when relevant
- If you don't find relevant information in the knowledge base, say so and provide general expertise

**RESPONSE FORMAT:**
- Start with a direct answer to the question
- Provide detailed analysis using the knowledge base
- End with actionable recommendations if applicable
"""
            )
            
            # Step 4: Format chat history
            chat_history_text = ""
            if st.session_state.chat_history:
                recent_history = st.session_state.chat_history[-6:]  # Last 6 messages
                for msg in recent_history:
                    if isinstance(msg, HumanMessage):
                        chat_history_text += f"Human: {msg.content}\n"
                    elif isinstance(msg, AIMessage):
                        chat_history_text += f"Assistant: {msg.content}\n"
            
            # Step 5: Generate response
            formatted_prompt = prompt.format(
                question=user_question,
                analytics_context=analytics_context,
                chat_history=chat_history_text
            )
            
            response = self.llm.invoke([HumanMessage(content=formatted_prompt)])
            
            # Step 6: Update chat history
            st.session_state.chat_history.append(HumanMessage(content=user_question))
            st.session_state.chat_history.append(AIMessage(content=response.content))
            
            return response.content
            
        except Exception as e:
            return f"❌ Error generating response: {e}"
    
    def render_chat_interface(self):
        """Render the main chat interface"""
        st.title("🚀 Analytics Chat Assistant")
        st.markdown("**Powered by GPT-4o + Analytics Events Knowledge Base (375+ events)**")
        
        # System status
        col1, col2, col3 = st.columns(3)
        with col1:
            status = "🟢 Connected" if self.analytics_index else "🔴 Disconnected"
            st.metric("📊 Knowledge Base", status)
        with col2:
            status = "🟢 Ready" if self.llm else "🔴 Not configured"
            st.metric("🧠 ChatGPT-4o", status)
        with col3:
            st.metric("💬 Messages", len(st.session_state.chat_messages))
        
        st.markdown("---")
        
        # Chat messages display
        self.render_chat_messages()
        
        # Chat input
        self.render_chat_input()
        
        # Sidebar with analytics tools
        self.render_analytics_sidebar()
    
    def render_chat_messages(self):
        """Render chat message history"""
        if not st.session_state.chat_messages:
            st.markdown("""
            ### 👋 Welcome to the Analytics Chat Assistant!
            
            **I can help you with:**
            - 📊 Understanding Mixpanel events and user behavior
            - 🔍 Debugging analytics issues
            - 📈 Analyzing user journeys and conversion funnels
            - 💡 Optimizing app performance and UX
            - 🎯 Interpreting user engagement patterns
            
            **Try asking:**
            - "What does the mpin_validated event mean?"
            - "How do users typically flow through onboarding?"
            - "What causes high drop-off rates?"
            - "Explain the difference between iOS and Android user behavior"
            """)
        else:
            for i, message in enumerate(st.session_state.chat_messages):
                if message["role"] == "user":
                    with st.chat_message("user"):
                        st.write(message["content"])
                        st.caption(f"🕐 {message.get('timestamp', '')}")
                else:
                    with st.chat_message("assistant"):
                        st.write(message["content"])
                        st.caption(f"🤖 {message.get('timestamp', '')} • {message.get('processing_info', 'GPT-4o + Analytics KB')}")
    
    def render_chat_input(self):
        """Render chat input area"""
        user_input = st.chat_input("Ask me anything about analytics, events, or user behavior...")
        
        if user_input:
            # Add user message
            timestamp = datetime.now().strftime("%H:%M:%S")
            st.session_state.chat_messages.append({
                "role": "user",
                "content": user_input,
                "timestamp": timestamp
            })
            
            # Generate response
            with st.spinner("🧠 Analyzing with GPT-4o + Analytics Knowledge Base..."):
                response = self.generate_enhanced_response(user_input)
            
            # Add assistant response
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "processing_info": "GPT-4o + 375+ Events"
            })
            
            # Rerun to show new messages
            st.rerun()
    
    def render_analytics_sidebar(self):
        """Render analytics tools sidebar"""
        with st.sidebar:
            st.header("🔧 Analytics Tools")
            
            # Event lookup tool
            st.subheader("🔍 Event Lookup")
            event_name = st.text_input("Enter event name:", placeholder="e.g., mpin_validated")
            
            if st.button("🔍 Lookup Event") and event_name:
                event_info = self.get_exact_event_info(event_name)
                if event_info:
                    st.success("✅ Event found!")
                    st.json(event_info)
                else:
                    # Try semantic search as fallback
                    results = self.search_analytics_knowledge(event_name, k=3)
                    if results:
                        st.info("📊 Similar events found:")
                        for result in results:
                            st.write(f"**{result['event_name']}** (score: {result['score']:.3f})")
                            st.write(result['description'][:100] + "...")
                    else:
                        st.error("❌ Event not found")
            
            # Quick search
            st.subheader("⚡ Quick Search")
            quick_searches = [
                "Login events",
                "Payment flow",
                "Onboarding process", 
                "Error events",
                "User engagement",
                "Mobile app events"
            ]
            
            for search_term in quick_searches:
                if st.button(f"🔍 {search_term}"):
                    # Add as user message and generate response
                    st.session_state.chat_messages.append({
                        "role": "user",
                        "content": f"Tell me about {search_term.lower()}",
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })
                    
                    response = self.generate_enhanced_response(f"Tell me about {search_term.lower()}")
                    
                    st.session_state.chat_messages.append({
                        "role": "assistant", 
                        "content": response,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "processing_info": "Quick Search"
                    })
                    st.rerun()
            
            # Analytics stats
            st.subheader("📊 Knowledge Base Stats")
            if self.analytics_index:
                try:
                    stats = self.analytics_index.describe_index_stats()
                    total_vectors = stats.total_vector_count
                    st.metric("📋 Total Events", f"{total_vectors:,}")
                    st.metric("🎯 Dimensions", DIMENSIONS)
                    st.metric("🔗 Index", ANALYTICS_KNOWLEDGE_INDEX)
                except:
                    st.info("📊 375+ events available")
            
            # Clear chat
            if st.button("🗑️ Clear Chat"):
                st.session_state.chat_messages = []
                st.session_state.chat_history = []
                st.rerun()

def main():
    """Main application entry point"""
    st.set_page_config(
        page_title="Analytics Chat Assistant",
        page_icon="🚀",
        layout="wide"
    )
    
    # Initialize assistant
    assistant = AnalyticsChatAssistant()
    
    # Render interface
    assistant.render_chat_interface()

if __name__ == "__main__":
    main() 