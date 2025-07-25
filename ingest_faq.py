import os
import re
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from pinecone import Pinecone, ServerlessSpec
import httpx

# Load environment variables
load_dotenv()

# Disable SSL verification
from network_utils import install_insecure_ssl
install_insecure_ssl()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
FAQ_INDEX_NAME = "faq"
DIMENSIONS = 512

def create_faq_index():
    """Create the FAQ index in Pinecone if it doesn't exist"""
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY, ssl_verify=False)
        
        # Check if index exists
        existing_indexes = pc.list_indexes().names()
        
        if FAQ_INDEX_NAME not in existing_indexes:
            print(f"🔧 Creating new Pinecone index: {FAQ_INDEX_NAME}")
            pc.create_index(
                name=FAQ_INDEX_NAME,
                dimension=DIMENSIONS,
                metric='cosine',
                spec=ServerlessSpec(
                    cloud='aws',
                    region='us-east-1'
                )
            )
            print(f"✅ Index '{FAQ_INDEX_NAME}' created successfully!")
        else:
            print(f"✅ Index '{FAQ_INDEX_NAME}' already exists")
            
        return pc.Index(FAQ_INDEX_NAME)
    
    except Exception as e:
        print(f"❌ Error creating FAQ index: {e}")
        return None

def parse_faq_file(file_path):
    """Parse FAQ.txt file into question-answer pairs"""
    print(f"📖 Reading FAQ file: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Split content into Q&A pairs
    # FAQ format: Question followed by answer, separated by empty lines or new questions
    qa_pairs = []
    
    # Split by lines and process
    lines = content.strip().split('\n')
    current_question = None
    current_answer = []
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            if current_question and current_answer:
                # Save current Q&A pair
                answer_text = ' '.join(current_answer).strip()
                if answer_text:
                    qa_pairs.append({
                        'question': current_question,
                        'answer': answer_text,
                        'full_text': f"Q: {current_question}\nA: {answer_text}"
                    })
                    print(f"✅ Parsed Q&A: {current_question[:50]}...")
                
                # Reset for next pair
                current_question = None
                current_answer = []
            continue
        
        # Check if line is a question (ends with ?)
        if line.endswith('?'):
            # Save previous Q&A if exists
            if current_question and current_answer:
                answer_text = ' '.join(current_answer).strip()
                if answer_text:
                    qa_pairs.append({
                        'question': current_question,
                        'answer': answer_text,
                        'full_text': f"Q: {current_question}\nA: {answer_text}"
                    })
                    print(f"✅ Parsed Q&A: {current_question[:50]}...")
            
            # Start new question
            current_question = line
            current_answer = []
        else:
            # This is part of the answer
            if current_question:
                current_answer.append(line)
    
    # Don't forget the last Q&A pair
    if current_question and current_answer:
        answer_text = ' '.join(current_answer).strip()
        if answer_text:
            qa_pairs.append({
                'question': current_question,
                'answer': answer_text,
                'full_text': f"Q: {current_question}\nA: {answer_text}"
            })
            print(f"✅ Parsed Q&A: {current_question[:50]}...")
    
    print(f"📊 Total Q&A pairs parsed: {len(qa_pairs)}")
    return qa_pairs

def create_documents_from_qa_pairs(qa_pairs):
    """Convert Q&A pairs into LangChain documents"""
    documents = []
    
    for i, qa_pair in enumerate(qa_pairs):
        # Create document with full Q&A text
        doc = Document(
            page_content=qa_pair['full_text'],
            metadata={
                'source': 'FAQ.txt',
                'question': qa_pair['question'],
                'answer': qa_pair['answer'],
                'type': 'faq',
                'faq_id': f"faq_{i+1}",
                'category': 'user_support'
            }
        )
        documents.append(doc)
        
        # Also create separate documents for question and answer for better search
        question_doc = Document(
            page_content=qa_pair['question'],
            metadata={
                'source': 'FAQ.txt',
                'question': qa_pair['question'],
                'answer': qa_pair['answer'],
                'type': 'faq_question',
                'faq_id': f"faq_{i+1}_q",
                'category': 'user_support'
            }
        )
        documents.append(question_doc)
        
        answer_doc = Document(
            page_content=qa_pair['answer'],
            metadata={
                'source': 'FAQ.txt',
                'question': qa_pair['question'],
                'answer': qa_pair['answer'],
                'type': 'faq_answer',
                'faq_id': f"faq_{i+1}_a",
                'category': 'user_support'
            }
        )
        documents.append(answer_doc)
    
    print(f"📄 Created {len(documents)} documents from Q&A pairs")
    return documents

def ingest_faq_to_pinecone():
    """Main function to ingest FAQ into Pinecone"""
    print("🚀 Starting FAQ ingestion to Pinecone...")
    
    # Create FAQ index
    faq_index = create_faq_index()
    if not faq_index:
        print("❌ Failed to create FAQ index. Exiting.")
        return False
    
    # Initialize embeddings
    print("🔧 Initializing OpenAI embeddings...")
    embeddings = OpenAIEmbeddings(
        api_key=OPENAI_API_KEY,
        model="text-embedding-3-small",
        dimensions=DIMENSIONS,
        http_client=httpx.Client(verify=False, timeout=30)
    )
    
    # Parse FAQ file
    faq_file_path = "resources/FAQ.txt"
    qa_pairs = parse_faq_file(faq_file_path)
    
    if not qa_pairs:
        print("❌ No Q&A pairs found in FAQ file")
        return False
    
    # Create documents
    documents = create_documents_from_qa_pairs(qa_pairs)
    
    # Create vector store and add documents
    print("📤 Uploading documents to Pinecone...")
    try:
        vector_store = PineconeVectorStore(
            index=faq_index,
            embedding=embeddings
        )
        
        # Add documents to vector store
        vector_store.add_documents(documents)
        
        print(f"✅ Successfully ingested {len(documents)} FAQ documents to Pinecone index '{FAQ_INDEX_NAME}'")
        
        # Test search
        print("\n🔍 Testing FAQ search...")
        test_query = "How to know if user login was successful?"
        results = vector_store.similarity_search(test_query, k=3)
        
        print(f"📊 Test search results for: '{test_query}'")
        for i, result in enumerate(results, 1):
            print(f"   {i}. {result.page_content[:100]}...")
            print(f"      Type: {result.metadata.get('type', 'unknown')}")
            print(f"      Question: {result.metadata.get('question', 'N/A')[:60]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error ingesting FAQ to Pinecone: {e}")
        return False

if __name__ == "__main__":
    success = ingest_faq_to_pinecone()
    if success:
        print("\n🎉 FAQ ingestion completed successfully!")
        print(f"📍 FAQ data is now available in Pinecone index: {FAQ_INDEX_NAME}")
        print("🤖 You can now query FAQ data through your chatbot!")
    else:
        print("\n❌ FAQ ingestion failed!") 