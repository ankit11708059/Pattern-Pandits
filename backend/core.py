import os
import httpx
import warnings
import ssl
from dotenv import load_dotenv
from langchain import hub
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain_core.prompts import ChatPromptTemplate
from pinecone import Pinecone

# Load environment variables from .env file
load_dotenv()

# Comprehensive SSL handling for development environment
warnings.filterwarnings("ignore", message="Unverified HTTPS request")
warnings.filterwarnings("ignore", category=UserWarning, module="langsmith")

# Set environment variables to disable SSL verification for LangChain/LangSmith
os.environ['LANGCHAIN_TRACING_V2'] = 'false'
os.environ['LANGSMITH_TRACING'] = 'false'
os.environ['LANGCHAIN_API_KEY'] = ''
os.environ['LANGSMITH_API_KEY'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['CURL_CA_BUNDLE'] = ''

# Create unverified SSL context
ssl._create_default_https_context = ssl._create_unverified_context

# Suppress specific LangSmith warnings
warnings.filterwarnings("ignore", message=".*LangSmith.*")
warnings.filterwarnings("ignore", message=".*api.smith.langchain.com.*")

INDEX_NAME="medium-blogs-embedding-index"

# Get API keys from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")


def run_llm(query: str):
    # Check for required API keys
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

    print(f"🔍 Running LLM query: {query}")
    print("🔧 Initializing OpenAI embeddings with SSL handling...")
    
    # Initialize embeddings with explicit API key and SSL handling (same as rag_utils.py)
    # Using dimensions=512 to match the Pinecone index (same as rag_utils.py)
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        dimensions=512,  # Match the Pinecone index dimensions
        openai_api_key=OPENAI_API_KEY,
        http_client=httpx.Client(verify=False, timeout=30)  # SSL handling
    )
    
    print("🔧 Connecting to Pinecone vector store with SSL handling...")
    # Initialize Pinecone with SSL disabled (same as rag_utils.py)
    pc = Pinecone(api_key=PINECONE_API_KEY, ssl_verify=False)
    index = pc.Index(INDEX_NAME)
    
    docsearch = PineconeVectorStore(index=index, embedding=embeddings)

    print("🔧 Initializing ChatOpenAI with SSL handling...")
    chat = ChatOpenAI(
        verbose=True, 
        temperature=0,
        openai_api_key=OPENAI_API_KEY,
        http_client=httpx.Client(verify=False, timeout=30)  # SSL handling
    )

    print("🔧 Loading retrieval QA prompt...")
    try:
        # Attempt to load prompt from hub with timeout
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        # Configure requests session with SSL disabled
        session = requests.Session()
        session.verify = False
        
        # Monkey patch requests for hub operations
        original_get = requests.get
        requests.get = lambda *args, **kwargs: original_get(*args, **{**kwargs, 'verify': False, 'timeout': 10})
        
        retrieval_qa_chat_prompt = hub.pull("langchain-ai/retrieval-qa-chat")
        print("✅ Successfully loaded prompt from LangChain hub")
        
        # Restore original requests.get
        requests.get = original_get
        
    except Exception as e:
        print(f"⚠️ LangChain hub connection failed (SSL/Network issue)")
        print("🔧 Using optimized fallback prompt...")
        # Enhanced fallback prompt
        retrieval_qa_chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert assistant for question-answering tasks. "
                      "Use the following retrieved context to provide accurate, helpful answers. "
                      "Guidelines:\n"
                      "- Base your answer primarily on the provided context\n"
                      "- If the context doesn't contain enough information, state this clearly\n"
                      "- Keep responses concise but comprehensive\n"
                      "- Include specific details when available\n\n"
                      "Context:\n{context}"),
            ("human", "Question: {input}"),
        ])

    print("🔧 Creating document chain...")
    stuff_documents_chain = create_stuff_documents_chain(chat, retrieval_qa_chat_prompt)

    print("🔧 Creating retrieval chain...")
    qa = create_retrieval_chain(
        retriever=docsearch.as_retriever(),
        combine_docs_chain=stuff_documents_chain
    )

    print("🚀 Executing query...")
    result = qa.invoke(input={"input": query})
    
    print("✅ Query completed successfully!")
    return result


if __name__ == "__main__":
    # Suppress stderr temporarily for cleaner output
    import sys
    from contextlib import redirect_stderr
    from io import StringIO
    
    try:
        print("🚀 Starting LLM query...")
        
        # Capture stderr to hide LangSmith connection errors
        stderr_capture = StringIO()
        with redirect_stderr(stderr_capture):
            result = run_llm("who wrote the article , slashing build times at slice")
        
        print("\n📋 Result:")
        print("=" * 50)
        print(result.get('answer', 'No answer found'))
        print("=" * 50)
        print("\n✅ RAG query completed successfully!")
        
    except ValueError as e:
        print(f"\n{e}")
        print("\n💡 To fix this:")
        print("1. Make sure you have a .env file in your project root")
        print("2. Add your OpenAI and Pinecone API keys to the .env file")
        print("3. Example .env file content:")
        print("   OPENAI_API_KEY=sk-your-openai-key-here")
        print("   PINECONE_API_KEY=your-pinecone-key-here")
    except Exception as e:
        print(f"❌ Error running LLM: {e}")
        print("💡 Make sure your Pinecone index exists and API keys are correct")