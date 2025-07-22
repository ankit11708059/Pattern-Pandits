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
import httpx        # For making HTTP requests with SSL handling
import warnings     # For suppressing unnecessary warning messages
import ssl          # For handling SSL certificates (security stuff)

# 🔧 Load environment variables from .env file (where we store secret API keys)
from dotenv import load_dotenv

# 🔗 LangChain imports - The main framework for building AI applications
from langchain import hub                                    # For loading pre-made prompts
from langchain.chains.combine_documents import create_stuff_documents_chain  # Combines documents into one context
from langchain.chains.retrieval import create_retrieval_chain               # Creates the full RAG pipeline
from langchain_openai import OpenAIEmbeddings, ChatOpenAI                   # OpenAI integrations
from langchain_pinecone import PineconeVectorStore                          # Pinecone database integration
from langchain_core.prompts import ChatPromptTemplate                       # For creating custom prompts

# 🗄️ Pinecone import - Vector database for storing and searching documents
from pinecone import Pinecone

# ------------------------------------------------------------------------------
# ⚙️ CONFIGURATION SETUP - Getting everything ready to work
# ------------------------------------------------------------------------------

# 🔑 Load all our secret API keys from the .env file
# This is CRITICAL - without this, we can't access OpenAI or Pinecone!
load_dotenv()

# 🔒 SSL HANDLING - Making sure our connections work even with certificate issues
# (This is like telling your browser "it's okay to visit this site even if the security certificate is weird")
warnings.filterwarnings("ignore", message="Unverified HTTPS request")     # Hide SSL warnings
warnings.filterwarnings("ignore", category=UserWarning, module="langsmith") # Hide LangSmith warnings

# 🚫 DISABLE TRACING - Turn off LangChain's tracking features (we don't need them)
# These would normally send data to LangSmith for monitoring, but we disable it
os.environ['LANGCHAIN_TRACING_V2'] = 'false'
os.environ['LANGSMITH_TRACING'] = 'false'
os.environ['LANGCHAIN_API_KEY'] = ''
os.environ['LANGSMITH_API_KEY'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''    # Disable SSL certificate checking
os.environ['CURL_CA_BUNDLE'] = ''        # Disable SSL certificate checking

# 🔓 Create unverified SSL context - This bypasses SSL certificate verification
# WARNING: Only use this in development! In production, you'd want proper SSL.
ssl._create_default_https_context = ssl._create_unverified_context

# 🤫 Suppress specific warnings that aren't important for our use case
warnings.filterwarnings("ignore", message=".*LangSmith.*")
warnings.filterwarnings("ignore", message=".*api.smith.langchain.com.*")

# ------------------------------------------------------------------------------
# 📋 GLOBAL CONFIGURATION - Settings that control how our system works
# ------------------------------------------------------------------------------

# 🗂️ The name of our Pinecone index (think of this as the name of our document database)
INDEX_NAME="medium-blogs-embedding-index"

# 🔑 Get our API keys from environment variables
# These are the "passwords" that let us use OpenAI and Pinecone services
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")      # For AI text generation and embeddings
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")  # For vector database access


# ==============================================================================
# 🧠 MAIN RAG FUNCTION - This is where the magic happens!
# ==============================================================================

def run_llm(query: str, context_size: str = "large"):
    """
    🎯 THE MAIN RAG FUNCTION - This does the heavy lifting!
    
    Here's what happens step by step:
    1. Check we have the right API keys
    2. Convert your question into numbers (embeddings) that computers understand
    3. Search our document database for similar content
    4. Use AI to generate a smart answer based on what we found
    
    Args:
        query: Your question (like "Who wrote the article about build times?")
        context_size: How much context to use:
                     - "small" (5 docs) = faster, less detailed
                     - "medium" (10 docs) = balanced
                     - "large" (20 docs) = more detailed (default)
                     - "max" (30 docs) = most comprehensive, slower
    
    Returns:
        A dictionary with 'answer' key containing the AI's response
    """
    
    # ------------------------------------------------------------------------------
    # 🔐 STEP 1: Security Check - Make sure we have valid API keys
    # ------------------------------------------------------------------------------
    
    # 🚨 Check if OpenAI API key exists and isn't the placeholder
    # Without this, we can't use AI to generate answers or create embeddings!
    if not OPENAI_API_KEY or OPENAI_API_KEY == "your_openai_api_key":
        raise ValueError(
            "❌ OpenAI API key not found! Please add your OpenAI API key to the .env file:\n"
            "OPENAI_API_KEY=your_actual_openai_key_here"
        )
    
    # 🚨 Check if Pinecone API key exists and isn't the placeholder  
    # Without this, we can't search through our document database!
    if not PINECONE_API_KEY or PINECONE_API_KEY == "your_pinecone_api_key":
        raise ValueError(
            "❌ Pinecone API key not found! Please add your Pinecone API key to the .env file:\n"
            "PINECONE_API_KEY=your_actual_pinecone_key_here"
        )
    
    # ------------------------------------------------------------------------------
    # 📏 STEP 2: Configure Context Size - How much information to retrieve
    # ------------------------------------------------------------------------------
    
    # 📊 This controls how many documents we'll retrieve for context
    # More documents = more detailed answers but slower processing and higher costs
    context_config = {
        "small": 5,    # Quick answers, basic context
        "medium": 10,  # Balanced approach  
        "large": 20,   # Detailed answers (DEFAULT)
        "max": 30      # Maximum detail, comprehensive coverage
    }
    # Get the number of documents for the requested context size (default to 20)
    k_value = context_config.get(context_size, 20)

    print(f"🔍 Running LLM query: {query}")
    print("🔧 Initializing OpenAI embeddings with SSL handling...")
    
    # ------------------------------------------------------------------------------
    # 🔢 STEP 3: Create Embeddings Model - Convert text to numbers computers understand
    # ------------------------------------------------------------------------------
    
    # 🧮 WHY DO WE NEED EMBEDDINGS?
    # Computers can't understand words like "cat" or "happy" - they only understand numbers
    # Embeddings solve this by converting text into arrays of numbers that represent meaning
    # 
    # WHAT DO EMBEDDINGS DO?
    # - "cat" might become [0.2, -0.1, 0.8, ...] (512 numbers)
    # - "dog" might become [0.3, -0.2, 0.7, ...] (similar numbers because cats and dogs are related)
    # - This lets us find documents about similar topics by comparing these number patterns
    #
    # REAL EXAMPLE:
    # Your question: "Who wrote the build article?" → [0.1, 0.4, -0.2, ...]
    # Document: "Build optimization by John" → [0.2, 0.3, -0.1, ...] (similar numbers = relevant!)
    # Document: "Cooking recipes" → [0.9, -0.8, 0.1, ...] (very different numbers = not relevant)
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",  # OpenAI's model that's good at understanding meaning
        dimensions=512,                   # Each text becomes exactly 512 numbers (like a fingerprint)
        openai_api_key=OPENAI_API_KEY,   # Our password to use OpenAI's service
        http_client=httpx.Client(verify=False, timeout=30)  # Technical: Handle network issues
    )
    # 🔑 KEY POINT: The 512 dimensions must match what we used when storing documents in Pinecone!
    
    print("🔧 Connecting to Pinecone vector store with SSL handling...")
    
    # ------------------------------------------------------------------------------
    # 🗄️ STEP 4: Connect to Pinecone Database - Where our documents are stored
    # ------------------------------------------------------------------------------
    
    # 🗄️ WHY DO WE NEED PINECONE?
    # Pinecone is like a super-smart library that can instantly find relevant books
    # Instead of searching by title, it searches by meaning using those number patterns (embeddings)
    # 
    # WHAT'S HAPPENING HERE?
    pc = Pinecone(api_key=PINECONE_API_KEY, ssl_verify=False)  # Connect to the Pinecone service
    
    # 📚 Open our specific "book collection" (index) where all our documents are stored
    # Think of INDEX_NAME as the name of our specialized library section
    index = pc.Index(INDEX_NAME)
    
    # 🔍 CREATE THE SMART SEARCH SYSTEM
    # This combines two powerful tools:
    # 1. Our embeddings (convert text to numbers)
    # 2. Pinecone database (find similar numbers super fast)
    # Result: We can ask "find documents about build optimization" and get relevant results instantly!
    docsearch = PineconeVectorStore(index=index, embedding=embeddings)

    print("🔧 Initializing ChatOpenAI with enhanced context handling...")
    
    # ------------------------------------------------------------------------------
    # 🤖 STEP 5: Setup AI Model - The brain that generates answers
    # ------------------------------------------------------------------------------
    
    # 🧠 WHY DO WE NEED ChatOpenAI?
    # This is the "brain" that actually reads the documents we found and writes intelligent answers
    # Think of it like a really smart research assistant who can:
    # - Read through dozens of documents instantly
    # - Understand the context and meaning
    # - Write a comprehensive, well-structured answer
    #
    # WHAT DO THESE SETTINGS DO?
    chat = ChatOpenAI(
        verbose=True,                     # Show us what's happening behind the scenes (helpful for debugging)
        temperature=0,                    # 0 = stick to facts, be consistent; 1 = be creative and vary answers
        model="gpt-3.5-turbo-16k",       # The "16k" means it can read 16,000 words at once (vs 4,000 for regular)
        max_tokens=4000,                  # Don't let the answer be longer than 4,000 words (prevents super long responses)
        openai_api_key=OPENAI_API_KEY,    # Our password to use OpenAI's AI service
        http_client=httpx.Client(verify=False, timeout=30)  # Technical: Handle network connection issues
    )
    # 🎯 ANALOGY: Like hiring a speed-reader who can read 16,000 words and summarize them perfectly!

    print("🔧 Loading retrieval QA prompt...")
    
    # ------------------------------------------------------------------------------
    # 📝 STEP 6: Setup Prompt Template - Instructions for the AI
    # ------------------------------------------------------------------------------
    
    try:
        # 🌐 Try to load a pre-made prompt from LangChain Hub (online repository)
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        # 🔧 Configure requests to work with SSL issues
        session = requests.Session()
        session.verify = False
        
        # 🐒 Temporarily modify requests to bypass SSL (monkey patching)
        original_get = requests.get
        requests.get = lambda *args, **kwargs: original_get(*args, **{**kwargs, 'verify': False, 'timeout': 10})
        
        # 📥 Try to download the official prompt from LangChain
        retrieval_qa_chat_prompt = hub.pull("langchain-ai/retrieval-qa-chat")
        print("✅ Successfully loaded prompt from LangChain hub")
        
        # 🔄 Restore the original requests function
        requests.get = original_get
        
    except Exception as e:
        # 🚨 If downloading fails (network issues, SSL problems), use our backup prompt
        print(f"⚠️ LangChain hub connection failed (SSL/Network issue)")
        print("🔧 Using optimized fallback prompt...")
        
        # 📋 FALLBACK PROMPT - Custom instructions for the AI when hub fails
        # This tells the AI exactly how to use the context we provide
        retrieval_qa_chat_prompt = ChatPromptTemplate.from_messages([
            ("system", 
             "You are an expert assistant for question-answering tasks with access to extensive context. "
             "Use the following comprehensive retrieved context to provide detailed, accurate answers. "
             "Guidelines:\n"
             "- Synthesize information from ALL provided context documents\n"      # Use everything!
             "- Cross-reference information across multiple sources when available\n"  # Compare sources
             "- Provide detailed answers with specific examples and evidence\n"     # Be specific
             "- Include relevant quotes or specific details from the context\n"     # Quote the source
             "- If context is extensive, organize your response with clear structure\n"  # Stay organized
             "- Mention if information comes from multiple sources\n"              # Show your sources
             "- If context doesn't contain enough information, state this clearly\n\n"  # Be honest
             "EXTENSIVE CONTEXT:\n{context}"),  # This is where retrieved docs go
            ("human", "Question: {input}"),  # This is where the user's question goes
        ])

    print("🔧 Creating document chain...")
    
    # ------------------------------------------------------------------------------
    # 🔗 STEP 7: Create Document Processing Chain - Combine docs with AI
    # ------------------------------------------------------------------------------
    
    # 📚 WHY DO WE NEED A DOCUMENT CHAIN?
    # The AI can only handle one conversation at a time, but we found multiple documents
    # This chain solves that by combining all documents into one organized "briefing"
    # 
    # WHAT DOES IT DO?
    # 1. Takes 5-30 separate documents we found
    # 2. Combines them into one large, organized text
    # 3. Adds our instructions (prompt) on how to use this information
    # 4. Sends everything to the AI as one complete "research briefing"
    # 
    # 🎯 ANALOGY: Like a research assistant gathering all relevant papers and creating 
    #              one organized report for the expert to read and analyze
    stuff_documents_chain = create_stuff_documents_chain(chat, retrieval_qa_chat_prompt)

    print("🔧 Creating enhanced retrieval chain with increased context...")
    
    # ------------------------------------------------------------------------------
    # 🔍 STEP 8: Configure Document Retrieval - How to find relevant docs
    # ------------------------------------------------------------------------------
    
    # 🎯 METHOD 1: Standard similarity search (CURRENTLY USED)
    # This finds documents most similar to your question
    enhanced_retriever = docsearch.as_retriever(
        search_type="similarity",         # Find most similar documents
        search_kwargs={
            "k": k_value,                 # Number of documents to retrieve (5-30)
        }
    )
    
    # 🌈 METHOD 2: MMR (Maximum Marginal Relevance) - ALTERNATIVE OPTION
    # Uncomment this to use diverse results instead of just most similar
    # enhanced_retriever = docsearch.as_retriever(
    #     search_type="mmr",
    #     search_kwargs={
    #         "k": 15,                      # Number of documents to return
    #         "lambda_mult": 0.7,           # 1.0 = only relevance, 0.0 = only diversity
    #     }
    # )
    
    # 🎯 METHOD 3: Score threshold - ALTERNATIVE OPTION  
    # Uncomment this to only get documents above a certain similarity score
    # enhanced_retriever = docsearch.as_retriever(
    #     search_type="similarity_score_threshold",
    #     search_kwargs={
    #         "k": 25,                      # Max documents to consider
    #         "score_threshold": 0.2,       # Minimum similarity score (0-1)
    #     }
    # )
    
    print(f"📄 Enhanced retriever configured to fetch up to {k_value} documents per query ({context_size} context)")
    
    # ------------------------------------------------------------------------------
    # 🏗️ STEP 9: Build Complete RAG Chain - Put it all together!
    # ------------------------------------------------------------------------------
    
    # 🔗 WHY DO WE NEED A RETRIEVAL CHAIN?
    # This is the "master coordinator" that connects all our pieces together
    # It manages the entire process from your question to the final answer
    # 
    # WHAT'S THE COMPLETE FLOW?
    # 1. You ask: "Who wrote the build article?"
    # 2. Retriever: Searches database, finds 20 relevant documents
    # 3. Document Chain: Combines those 20 documents into one organized briefing
    # 4. AI: Reads the briefing and writes a comprehensive answer
    # 5. You get: "The article was written by Saurabh Sachdeva, Senior Android Engineer..."
    # 
    # 🎯 ANALOGY: Like having a personal research team that automatically finds sources,
    #              organizes them, and provides expert analysis all in seconds!
    qa = create_retrieval_chain(
        retriever=enhanced_retriever,      # The "document finder"
        combine_docs_chain=stuff_documents_chain  # The "document organizer + AI analyst"
    )

    print("🚀 Executing enhanced query with increased context...")
    
    # ------------------------------------------------------------------------------
    # 🎯 STEP 10: Execute the Query - Run the entire RAG pipeline!
    # ------------------------------------------------------------------------------
    
    # 🚀 THE MAGIC MOMENT - EVERYTHING COMES TOGETHER!
    # Here's exactly what happens when you ask a question:
    # 
    # STEP-BY-STEP BREAKDOWN:
    # 1. Your question "Who wrote the build article?" becomes numbers [0.1, 0.4, -0.2, ...]
    # 2. Pinecone searches millions of document numbers to find the most similar ones
    # 3. We get back 5-30 highly relevant documents about build articles
    # 4. All documents get combined into one big "research report" 
    # 5. The AI reads this report + your question and writes a detailed answer
    # 6. You get back not just an answer, but the sources and context too!
    # 
    # 💫 THINK OF IT AS: Having a team of researchers, a librarian, and a PhD expert 
    #                    all working together in milliseconds to answer your question!
    result = qa.invoke(input={"input": query})
    
    # ------------------------------------------------------------------------------
    # 📊 STEP 11: Display Debug Info - Show what we retrieved
    # ------------------------------------------------------------------------------
    
    # 🔍 This helps you understand what documents were used to answer your question
    print("📊 Context Analysis:")
    if 'context' in result:
        context_docs = result['context']  # The documents that were retrieved
        print(f"   • Retrieved {len(context_docs)} documents")
        
        # 📏 Calculate total amount of text context
        total_chars = sum(len(doc.page_content) for doc in context_docs)
        print(f"   • Total context characters: {total_chars:,}")
        print(f"   • Average document length: {total_chars // len(context_docs) if context_docs else 0} chars")
        
        # 👀 Show previews of the first few documents
        print("📄 Document previews:")
        for i, doc in enumerate(context_docs[:3]):  # Show first 3 documents
            # Truncate long documents to 200 characters for preview
            preview = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            print(f"   Doc {i+1}: {preview}")
    
    print("✅ Enhanced query completed successfully!")
    return result  # Return the AI's answer plus metadata


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
            ("who wrote the article , slashing build times at slice", "max"),     # Maximum context
            ("what are the main build optimization techniques mentioned", "large") # Large context
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