#!/usr/bin/env python3
"""
Ingest events_pattern_pandit.csv into Pinecone event-catalog index
This script will read the CSV file and create embeddings for better AI insights
"""

import os
import csv
import httpx
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec
import sys

# ---------------------------------------------------------------------------
# Disable SSL verification globally (work-around for self-signed certificates)
# ---------------------------------------------------------------------------
from network_utils import install_insecure_ssl

install_insecure_ssl()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT", "aws-us-east-1")
INDEX_NAME = "event-catalog"
DIMENSIONS = 512
CSV_PATH = "resources/events_pattern_pandit.csv"

def main():
    """Main function to ingest events data"""
    print("🚀 Starting Pattern Pandits Events Ingestion...")
    
    # Validate configuration
    if not OPENAI_KEY:
        print("❌ OPENAI_API_KEY missing in environment")
        sys.exit(1)
    if not PINECONE_KEY:
        print("❌ PINECONE_API_KEY missing in environment")
        sys.exit(1)
    
    # Check if CSV exists
    if not os.path.exists(CSV_PATH):
        print(f"❌ CSV file not found at {CSV_PATH}")
        sys.exit(1)
    
    print(f"✅ Found CSV file: {CSV_PATH}")
    
    # ---------------------------------------------------------------------------
    # Load events catalog from CSV
    # ---------------------------------------------------------------------------
    print("📖 Loading events from CSV...")
    records = []
    try:
        with open(CSV_PATH, newline="", encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip empty rows
                if not row.get("Event Name", "").strip():
                    continue
                
                event_name = row.get("Event Name", "").strip()
                event_description = row.get("Event Description", "").strip()
                
                if event_name and event_description:
                    records.append({
                        "event_name": event_name,
                        "description": event_description
                    })
        
        print(f"✅ Loaded {len(records)} events from CSV")
        
        # Show sample records
        if records:
            print("\n📋 Sample events:")
            for i, record in enumerate(records[:3]):
                print(f"  {i+1}. {record['event_name']}: {record['description'][:100]}...")
    
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        sys.exit(1)
    
    if not records:
        print("❌ No valid records found in CSV")
        sys.exit(1)
    
    # ---------------------------------------------------------------------------
    # Initialize OpenAI Embeddings
    # ---------------------------------------------------------------------------
    print("🧠 Initializing OpenAI embeddings...")
    try:
        emb_model = OpenAIEmbeddings(
            api_key=OPENAI_KEY,
            model="text-embedding-3-small",
            dimensions=DIMENSIONS,
            http_client=httpx.Client(verify=False, timeout=30),
        )
        print("✅ OpenAI embeddings model initialized")
    except Exception as e:
        print(f"❌ Error initializing embeddings: {e}")
        sys.exit(1)
    
    # ---------------------------------------------------------------------------
    # Generate embeddings for event descriptions
    # ---------------------------------------------------------------------------
    print("🔢 Generating embeddings for event descriptions...")
    try:
        vectors = []
        for i, record in enumerate(records):
            # Create embedding for the event description
            description = record["description"]
            embedding = emb_model.embed_query(description)
            
            # Create vector tuple (id, embedding, metadata)
            vector_id = record["event_name"]
            metadata = {
                "event_name": record["event_name"],
                "description": record["description"],
                "text": record["description"]  # Add text field for LangChain compatibility
            }
            
            vectors.append((vector_id, embedding, metadata))
            
            if (i + 1) % 10 == 0:
                print(f"  Generated embeddings for {i + 1}/{len(records)} events")
        
        print(f"✅ Generated {len(vectors)} embeddings")
    
    except Exception as e:
        print(f"❌ Error generating embeddings: {e}")
        sys.exit(1)
    
    # ---------------------------------------------------------------------------
    # Initialize Pinecone and create/update index
    # ---------------------------------------------------------------------------
    print("🗄️ Connecting to Pinecone...")
    try:
        pc = Pinecone(api_key=PINECONE_KEY, ssl_verify=False)
        
        # Check if index exists, create if it doesn't
        existing_indexes = [index.name for index in pc.list_indexes()]
        
        if INDEX_NAME not in existing_indexes:
            print(f"📦 Creating new Pinecone index: {INDEX_NAME}")
            
            # Parse environment for cloud and region
            if "-" in PINECONE_ENV:
                parts = PINECONE_ENV.split("-", 1)
                cloud = parts[0]
                region = parts[1]
            else:
                cloud = "aws"
                region = PINECONE_ENV

            pc.create_index(
                name=INDEX_NAME,
                dimension=DIMENSIONS,
                metric="cosine",
                spec=ServerlessSpec(cloud=cloud, region=region),
            )
            print(f"✅ Created index: {INDEX_NAME}")
        else:
            print(f"✅ Using existing index: {INDEX_NAME}")
        
        # Get index reference
        index = pc.Index(INDEX_NAME)
        
    except Exception as e:
        print(f"❌ Error connecting to Pinecone: {e}")
        sys.exit(1)
    
    # ---------------------------------------------------------------------------
    # Upsert vectors to Pinecone
    # ---------------------------------------------------------------------------
    print("📤 Upserting vectors to Pinecone...")
    try:
        # Upsert in batches of 100
        batch_size = 100
        total_upserted = 0
        
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            index.upsert(batch)
            total_upserted += len(batch)
            print(f"  Upserted {total_upserted}/{len(vectors)} vectors")
        
        print(f"✅ Successfully upserted {len(vectors)} event vectors to {INDEX_NAME}")
        
        # Verify the upsert
        stats = index.describe_index_stats()
        print(f"📊 Index stats: {stats['total_vector_count']} total vectors")
        
    except Exception as e:
        print(f"❌ Error upserting to Pinecone: {e}")
        sys.exit(1)
    
    print("\n🎉 Events ingestion completed successfully!")
    print(f"📋 Total events processed: {len(records)}")
    print(f"🗄️ Index: {INDEX_NAME}")
    print(f"🧠 Embeddings model: text-embedding-3-small ({DIMENSIONS}D)")
    print("\n💡 Your Mixpanel app can now use these events for enhanced AI insights!")


if __name__ == "__main__":
    main() 