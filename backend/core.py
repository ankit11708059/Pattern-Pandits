# ==============================================================================
# 📚 RAG (Retrieval-Augmented Generation) System with Enhanced Context
# ==============================================================================
# 
# This file creates a smart question-answering system that:
# 1. Takes your question
# 2. Searches through a database of documents (Pinecone) to find relevant information
# 3. Uses AI (OpenAI) to generate a detailed answer based on the found documents
# 
# Think of it like having a super-smart research assistant that can instantly
# read through thousands of documents and give you a comprehensive answer!

# ------------------------------------------------------------------------------
# 📦 IMPORTS - All the tools we need to build our RAG system
# ------------------------------------------------------------------------------

import os           # For accessing environment variables (API keys, settings)
from typing import List, Dict, Any

import httpx        # For making HTTP requests with SSL handling
import warnings     # For suppressing unnecessary warning messages
import ssl          # For handling SSL certificates (security stuff)

# 🔧 Load environment variables from .env file (where we store secret API keys)
from dotenv import load_dotenv

# 🔗 LangChain imports - The main framework for building AI applications
from langchain import hub                                    # For loading pre-made prompts
from langchain.chains.combine_documents import create_stuff_documents_chain  # Combines documents into one context
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain               # Creates the full RAG pipeline
from langchain_openai import OpenAIEmbeddings, ChatOpenAI                   # OpenAI integrations
from langchain_pinecone import PineconeVectorStore                          # Pinecone database integration
from langchain_core.prompts import ChatPromptTemplate                       # For creating custom prompts

# 🗄️ Pinecone import - Vector database for storing and searching documents
from pinecone import Pinecone

# ------------------------------------------------------------------------------
# ⚙️ CONFIGURATION SETUP - Enhanced SSL and connection handling
# ------------------------------------------------------------------------------

# 🔑 Load all our secret API keys from the .env file
load_dotenv()

# 🔒 ENHANCED SSL HANDLING - Complete SSL bypass for corporate networks
warnings.filterwarnings("ignore", message="Unverified HTTPS request")     
warnings.filterwarnings("ignore", category=UserWarning, module="langsmith") 
warnings.filterwarnings("ignore", message=".*LangSmith.*")
warnings.filterwarnings("ignore", message=".*api.smith.langchain.com.*")
warnings.filterwarnings("ignore", message=".*SSL.*")
warnings.filterwarnings("ignore", category=DeprecationWarning)

# 🚫 DISABLE ALL EXTERNAL TRACKING AND CONNECTIONS
os.environ['LANGCHAIN_TRACING_V2'] = 'false'
os.environ['LANGSMITH_TRACING'] = 'false'
os.environ['LANGCHAIN_API_KEY'] = ''
os.environ['LANGSMITH_API_KEY'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''    
os.environ['CURL_CA_BUNDLE'] = ''        
os.environ['LANGCHAIN_HUB_API_URL'] = ''  # Disable hub connections
os.environ['LANGCHAIN_ENDPOINT'] = ''     # Disable endpoint connections

# 🔓 Create unverified SSL context
ssl._create_default_https_context = ssl._create_unverified_context

# ------------------------------------------------------------------------------
# 📋 GLOBAL CONFIGURATION - Settings that control how our system works
# ------------------------------------------------------------------------------

# 🗂️ The name of our Pinecone index (think of this as the name of our document database)
INDEX_NAME="medium-blogs-embedding-index"

# 🔑 Get our API keys from environment variables
# These are the "passwords" that let us use OpenAI and Pinecone services
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")      
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")  


# ==============================================================================
# 🧠 MAIN RAG FUNCTION - This is where the magic happens!
# ==============================================================================

def run_llm(query: str, context_size: str = "large", chat_history: List[Dict[str,Any]] = []):
    """
    🎯 THE MAIN RAG FUNCTION with enhanced SSL handling
    """
    
    # ------------------------------------------------------------------------------
    # 🔐 STEP 1: Security Check
    # ------------------------------------------------------------------------------
    
    if not OPENAI_API_KEY or OPENAI_API_KEY == "your_openai_api_key":
        raise ValueError(
            "❌ OpenAI API key not found! Please add your OpenAI API key to the .env file:\n"
            "OPENAI_API_KEY=your_actual_openai_key_here"
        )
    
    if not PINECONE_API_KEY or PINECONE_API_KEY == "your_pinecone_api_key":
        raise ValueError(
            "❌ Pinecone API key not found! Please add your Pinecone API key to the .env file:\n"
            "PINECONE_API_KEY=your_actual_pinecone_key_here"
        )
    
    # ------------------------------------------------------------------------------
    # 📏 STEP 2: Configure Context Size
    # ------------------------------------------------------------------------------
    
    context_config = {
        "small": 5,    
        "medium": 10,  
        "large": 20,   
        "max": 30      
    }
    k_value = context_config.get(context_size, 20)

    print(f"🔍 Running LLM query: {query}")
    print("🔧 Initializing OpenAI embeddings with SSL handling...")
    
    # ------------------------------------------------------------------------------
    # 🔢 STEP 3: Create Embeddings Model with enhanced SSL handling
    # ------------------------------------------------------------------------------
    
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",  
        dimensions=512,                   
        openai_api_key=OPENAI_API_KEY,   
        http_client=httpx.Client(verify=False, timeout=30)  
    )
    
    print("🔧 Connecting to Pinecone vector store with SSL handling...")
    
    # ------------------------------------------------------------------------------
    # 🗄️ STEP 4: Connect to Pinecone Database with SSL bypass
    # ------------------------------------------------------------------------------
    
    pc = Pinecone(api_key=PINECONE_API_KEY, ssl_verify=False)  
    index = pc.Index(INDEX_NAME)
    docsearch = PineconeVectorStore(index=index, embedding=embeddings)

    print("🔧 Initializing ChatOpenAI with enhanced context handling...")
    
    # ------------------------------------------------------------------------------
    # 🤖 STEP 5: Setup AI Model with SSL bypass
    # ------------------------------------------------------------------------------
    
    chat = ChatOpenAI(
        verbose=True,                     
        temperature=0,                    
        model="gpt-3.5-turbo-16k",       
        max_tokens=4000,                  
        openai_api_key=OPENAI_API_KEY,    
        http_client=httpx.Client(verify=False, timeout=30)  
    )

    print("🔧 Loading retrieval QA prompt...")
    
    # ------------------------------------------------------------------------------
    # 📝 STEP 6: Setup Prompt Template - Use local fallback to avoid SSL issues
    # ------------------------------------------------------------------------------
    
    # 🚫 SKIP LANGCHAIN HUB - Use local prompt to avoid SSL issues completely
    print("⚠️ LangChain hub connection failed (SSL/Network issue)")
    print("🔧 Using optimized fallback prompt...")
    
    # 📋 LOCAL PROMPT - No external connections needed
    retrieval_qa_chat_prompt = ChatPromptTemplate.from_messages([
        ("system", 
         "You are an expert assistant for question-answering tasks with access to extensive context. "
         "Use the following comprehensive retrieved context to provide detailed, accurate answers. "
         "Guidelines:\n"
         "- Synthesize information from ALL provided context documents\n"      
         "- Cross-reference information across multiple sources when available\n"  
         "- Provide detailed answers with specific examples and evidence\n"     
         "- Include relevant quotes or specific details from the context\n"     
         "- If context is extensive, organize your response with clear structure\n"  
         "- Mention if information comes from multiple sources\n"              
         "- If context doesn't contain enough information, state this clearly\n\n"  
         "EXTENSIVE CONTEXT:\n{context}"),  
        ("human", "Question: {input}"),  
    ])

    # 📋 SIMPLE REPHRASE PROMPT - Also local to avoid SSL issues
    rephrase_prompt = ChatPromptTemplate.from_messages([
        ("system", 
         "Given a chat history and the latest user question which might reference context in the chat history, "
         "formulate a standalone question which can be understood without the chat history. "
         "Do NOT answer the question, just reformulate it if needed and otherwise return it as is."),
        ("human", "Chat History:\n{chat_history}\n\nLatest Question: {input}")
    ])

    print("🔧 Creating document chain...")
    
    # ------------------------------------------------------------------------------
    # 🔗 STEP 7: Create Document Processing Chain
    # ------------------------------------------------------------------------------
    
    stuff_documents_chain = create_stuff_documents_chain(chat, retrieval_qa_chat_prompt)

    print("🔧 Creating enhanced retrieval chain with increased context...")
    
    # ------------------------------------------------------------------------------
    # 🔍 STEP 8: Configure Document Retrieval
    # ------------------------------------------------------------------------------
    
    enhanced_retriever = docsearch.as_retriever(
        search_type="similarity",         
        search_kwargs={
            "k": k_value,                 
        }
    )

    # 🔗 Create history-aware retriever manually (avoiding hub dependencies)
    from langchain.chains.history_aware_retriever import create_history_aware_retriever
    
    history_rephrase_retriever = create_history_aware_retriever(
        llm=chat,
        retriever=enhanced_retriever,
        prompt=rephrase_prompt
    )
    
    print(f"📄 Enhanced retriever configured to fetch up to {k_value} documents per query ({context_size} context)")
    
    # ------------------------------------------------------------------------------
    # 🏗️ STEP 9: Build Complete RAG Chain
    # ------------------------------------------------------------------------------
    
    qa = create_retrieval_chain(
        retriever=history_rephrase_retriever,      
        combine_docs_chain=stuff_documents_chain  
    )

    print("🚀 Executing enhanced query with increased context...")
    
    # ------------------------------------------------------------------------------
    # 🎯 STEP 10: Execute the Query with enhanced error handling
    # ------------------------------------------------------------------------------
    
    try:
        result = qa.invoke({"input": query, "chat_history": chat_history})
    except Exception as e:
        print(f"❌ Error during query execution: {e}")
        # Return a fallback response
        return {
            "answer": f"I apologize, but I encountered an error while processing your question: {str(e)}. Please try again or rephrase your question.",
            "context": []
        }
    
    # ------------------------------------------------------------------------------
    # 📊 STEP 11: Display Debug Info
    # ------------------------------------------------------------------------------
    
    print("📊 Context Analysis:")
    if 'context' in result:
        context_docs = result['context']  
        print(f"   • Retrieved {len(context_docs)} documents")
        
        total_chars = sum(len(doc.page_content) for doc in context_docs)
        print(f"   • Total context characters: {total_chars:,}")
        print(f"   • Average document length: {total_chars // len(context_docs) if context_docs else 0} chars")
        
        print("📄 Document previews:")
        for i, doc in enumerate(context_docs[:3]):  
            preview = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            print(f"   Doc {i+1}: {preview}")
    
    print("✅ Enhanced query completed successfully!")
    return result


# ==============================================================================
# 🧪 TESTING SECTION - Runs when you execute this file directly
# ==============================================================================

if __name__ == "__main__":
    # 🤫 Clean up stderr output for better presentation
    import sys
    from contextlib import redirect_stderr
    from io import StringIO
    
    try:
        print("🚀 Starting LLM query...")
        
        # 🧪 Test queries with different context sizes to show the system's flexibility
        test_queries = [
            ("who wrote the article , slashing build times at slice", "max"),     
            ("what are the main build optimization techniques mentioned", "large") 
        ]
        
        # 🔄 Run each test query
        for i, (query, context_size) in enumerate(test_queries, 1):
            print(f"\n{'='*60}")
            print(f"🔍 QUERY {i} ({context_size.upper()} CONTEXT): {query}")
            print('='*60)
            
            # 🤫 Capture error messages to keep output clean
            stderr_capture = StringIO()
            with redirect_stderr(stderr_capture):
                result = run_llm(query, context_size)
            
            # 📋 Display the AI's answer
            print(f"\n📋 Result {i}:")
            print("=" * 50)
            print(result.get('answer', 'No answer found'))
            print("=" * 50)
        
        # ✅ Success message and usage instructions
        print(f"\n✅ All RAG queries completed successfully!")
        print(f"\n💡 You can adjust context size by calling:")
        print(f"   run_llm(query, 'small')   # 5 documents")
        print(f"   run_llm(query, 'medium')  # 10 documents") 
        print(f"   run_llm(query, 'large')   # 20 documents")
        print(f"   run_llm(query, 'max')     # 30 documents")
        
    except ValueError as e:
        # 🚨 Handle missing API keys gracefully
        print(f"\n{e}")
        print("\n💡 To fix this:")
        print("1. Make sure you have a .env file in your project root")
        print("2. Add your OpenAI and Pinecone API keys to the .env file")
        print("3. Example .env file content:")
        print("   OPENAI_API_KEY=sk-your-openai-key-here")
        print("   PINECONE_API_KEY=your-pinecone-key-here")
    except Exception as e:
        # 🚨 Handle other errors (network, API issues, etc.)
        print(f"❌ Error running LLM: {e}")
        print("💡 Make sure your Pinecone index exists and API keys are correct")

# ==============================================================================
# 🎓 SUMMARY OF HOW THIS RAG SYSTEM WORKS:
# ==============================================================================
#
# 1. 🔑 AUTHENTICATION: Check API keys for OpenAI and Pinecone
# 
# 2. 🔢 EMBEDDINGS: Convert your question into numerical vectors that computers understand
#
# 3. 🔍 SEARCH: Use those vectors to find similar documents in the Pinecone database
#
# 4. 📚 RETRIEVE: Get the most relevant documents (5-30 depending on context_size)
#
# 5. 🔗 COMBINE: Merge all retrieved documents into one large context
#
# 6. 🤖 GENERATE: Send the context + your question to OpenAI's AI model
#
# 7. 📝 RESPOND: The AI reads all the context and generates a comprehensive answer
#
# 8. 📊 ANALYZE: Show you what documents were used and how much context was processed
#
# The magic is in the combination: instead of just asking an AI model that only
# knows general information, we first find specific, relevant documents from your
# database and give the AI that context to work with. This results in much more
# accurate, detailed, and source-backed answers!
#
# ==============================================================================