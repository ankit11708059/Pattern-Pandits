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


def run_llm(query: str, context_size: str = "large"):
    """
    Run LLM query with configurable context size
    
    Args:
        query: The question to ask
        context_size: "small" (5 docs), "medium" (10 docs), "large" (20 docs), "max" (30 docs)
    """
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
    
    # Configure context size
    context_config = {
        "small": 5,
        "medium": 10, 
        "large": 20,
        "max": 30
    }
    k_value = context_config.get(context_size, 20)

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

    print("🔧 Initializing ChatOpenAI with enhanced context handling...")
    chat = ChatOpenAI(
        verbose=True, 
        temperature=0,
        model="gpt-3.5-turbo-16k",  # Use 16k model for larger context
        max_tokens=4000,  # Increased token limit for longer responses
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
        # Enhanced fallback prompt optimized for large context
        retrieval_qa_chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert assistant for question-answering tasks with access to extensive context. "
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

    print("🔧 Creating document chain...")
    stuff_documents_chain = create_stuff_documents_chain(chat, retrieval_qa_chat_prompt)

    print("🔧 Creating enhanced retrieval chain with increased context...")
    
    # Method 1: Configurable similarity search 
    enhanced_retriever = docsearch.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": k_value,  # Configurable based on context_size parameter
        }
    )
    
    # Method 2: Alternative - Use MMR for diversity (uncomment to use)
    # enhanced_retriever = docsearch.as_retriever(
    #     search_type="mmr",
    #     search_kwargs={
    #         "k": 15,  # Number of documents to return
    #         "lambda_mult": 0.7,  # Balance between relevance (1.0) and diversity (0.0)
    #     }
    # )
    
    # Method 3: Alternative - Similarity with score threshold (uncomment to use)
    # enhanced_retriever = docsearch.as_retriever(
    #     search_type="similarity_score_threshold",
    #     search_kwargs={
    #         "k": 25,
    #         "score_threshold": 0.2,  # Lower threshold = more results
    #     }
    # )
    
    print(f"📄 Enhanced retriever configured to fetch up to {k_value} documents per query ({context_size} context)")
    
    qa = create_retrieval_chain(
        retriever=enhanced_retriever,
        combine_docs_chain=stuff_documents_chain
    )

    print("🚀 Executing enhanced query with increased context...")
    result = qa.invoke(input={"input": query})
    
    # Display context information for debugging
    print("📊 Context Analysis:")
    if 'context' in result:
        context_docs = result['context']
        print(f"   • Retrieved {len(context_docs)} documents")
        total_chars = sum(len(doc.page_content) for doc in context_docs)
        print(f"   • Total context characters: {total_chars:,}")
        print(f"   • Average document length: {total_chars // len(context_docs) if context_docs else 0} chars")
        
        # Show first few document previews
        print("📄 Document previews:")
        for i, doc in enumerate(context_docs[:3]):
            preview = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            print(f"   Doc {i+1}: {preview}")
    
    print("✅ Enhanced query completed successfully!")
    return result


if __name__ == "__main__":
    # Suppress stderr temporarily for cleaner output
    import sys
    from contextlib import redirect_stderr
    from io import StringIO
    
    try:
        print("🚀 Starting LLM query...")
        
        # Test different context sizes
        test_queries = [
            ("who wrote the article , slashing build times at slice", "max"),
            ("what are the main build optimization techniques mentioned", "large")
        ]
        
        for i, (query, context_size) in enumerate(test_queries, 1):
            print(f"\n{'='*60}")
            print(f"🔍 QUERY {i} ({context_size.upper()} CONTEXT): {query}")
            print('='*60)
            
            # Capture stderr to hide LangSmith connection errors
            stderr_capture = StringIO()
            with redirect_stderr(stderr_capture):
                result = run_llm(query, context_size)
            
            print(f"\n📋 Result {i}:")
            print("=" * 50)
            print(result.get('answer', 'No answer found'))
            print("=" * 50)
        
        print(f"\n✅ All RAG queries completed successfully!")
        print(f"\n💡 You can adjust context size by calling:")
        print(f"   run_llm(query, 'small')   # 5 documents")
        print(f"   run_llm(query, 'medium')  # 10 documents") 
        print(f"   run_llm(query, 'large')   # 20 documents")
        print(f"   run_llm(query, 'max')     # 30 documents")
        
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