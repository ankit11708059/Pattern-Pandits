#!/usr/bin/env python3
"""
Analytics Chat Assistant Launcher
Run this script to launch different versions of the analytics chat assistant
"""

import streamlit as st
import subprocess
import sys
import os

def main():
    st.set_page_config(
        page_title="Analytics Chat Assistant Launcher",
        page_icon="🚀",
        layout="centered"
    )
    
    st.title("🚀 Analytics Chat Assistant Launcher")
    st.markdown("**Choose your analytics chat experience**")
    
    # Option cards
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 📊 Basic Analytics Chat
        
        **Features:**
        - ChatOpenAI (GPT-4o) integration
        - Analytics knowledge base access
        - Clean chat interface
        - Event lookup tools
        - Quick search functionality
        
        **Best for:**
        - Quick event lookups
        - Simple Q&A about analytics
        - Learning about events
        """)
        
        if st.button("🚀 Launch Basic Chat", key="basic"):
            st.success("✅ Launching Basic Analytics Chat...")
            st.markdown("**Run this command in your terminal:**")
            st.code("streamlit run analytics_chat_assistant.py --server.port 8502")
    
    with col2:
        st.markdown("""
        ### 🧠 Enhanced Analytics Chat
        
        **Features:**
        - Advanced conversation memory
        - Session insights & analytics
        - Smart follow-up suggestions
        - Event categorization
        - Deep dive analysis
        - Conversation export
        - Beautiful enhanced UI
        
        **Best for:**
        - Complex analytics discussions
        - Ongoing analysis sessions
        - Team collaboration
        """)
        
        if st.button("🚀 Launch Enhanced Chat", key="enhanced"):
            st.success("✅ Launching Enhanced Analytics Chat...")
            st.markdown("**Run this command in your terminal:**")
            st.code("streamlit run enhanced_analytics_chat.py --server.port 8503")
    
    st.markdown("---")
    
    # Integration with existing system
    st.markdown("""
    ### 🔧 Integration with Existing System
    
    **Your existing `mixpanel_user_activity.py` already has:**
    - Sophisticated chat integration
    - Analytics knowledge base access
    - Mixpanel data integration
    - Beautiful modern UI
    
    **These new chat assistants provide:**
    - **Dedicated analytics focus** - Pure analytics Q&A without data loading
    - **Expert system prompts** - Specialized for analytics consulting
    - **Enhanced memory** - Better conversation continuity
    - **Advanced features** - Event categorization, insights, export
    """)
    
    # Quick access buttons
    st.markdown("### ⚡ Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔍 Run Original Mixpanel App"):
            st.success("✅ Launching Mixpanel User Activity...")
            st.code("streamlit run mixpanel_user_activity.py --server.port 8501")
    
    with col2:
        if st.button("📊 Check Analytics Knowledge Base"):
            st.info("📋 Analytics Events Knowledge Base Details:")
            st.markdown("""
            - **Index**: analytics-events-knowledge-base-512
            - **Dimensions**: 512
            - **Events**: 375+ detailed descriptions
            - **Categories**: Authentication, Payment, Onboarding, Navigation, etc.
            """)
    
    with col3:
        if st.button("🛠️ System Requirements"):
            st.info("📋 Required Environment Variables:")
            st.markdown("""
            ```bash
            OPENAI_API_KEY=your_openai_key
            PINECONE_API_KEY=your_pinecone_key
            ```
            
            **Dependencies:**
            - streamlit
            - langchain-openai
            - langchain-pinecone
            - pinecone-client
            - httpx
            """)
    
    st.markdown("---")
    st.markdown("💡 **Tip**: Each chat assistant runs on a different port so you can run multiple versions simultaneously!")

if __name__ == "__main__":
    main() 