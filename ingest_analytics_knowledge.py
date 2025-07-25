import os, csv, httpx, json, re
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()
OPENAI_KEY   = os.getenv("OPENAI_API_KEY")
PINECONE_KEY = os.getenv("PINECONE_API_KEY")
# PINECONE_ENVIRONMENT should look like "aws-us-east-1" or "gcp-starter"
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT", "aws-us-east-1")
INDEX_NAME   = "analytics-event-knowledge"
DIMENSIONS   = 512
KNOWLEDGE_PATH = "resources/analytics_events_knowledge_base.txt"

assert OPENAI_KEY, "OPENAI_API_KEY missing"
assert PINECONE_KEY, "PINECONE_API_KEY missing"

def parse_analytics_knowledge(file_path):
    """Parse the comprehensive analytics knowledge base with markdown structure"""
    records = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split into sections based on event headers (#### **event_name**)
    event_pattern = r'#### \*\*(.*?)\*\*\n(.*?)(?=#### \*\*|\Z)'
    event_matches = re.findall(event_pattern, content, re.DOTALL)
    
    record_id = 1
    
    for event_name, event_content in event_matches:
        event_name = event_name.strip()
        event_content = event_content.strip()
        
        if not event_name or not event_content:
            continue
        
        # Parse event details
        event_record = parse_event_details(event_name, event_content, record_id)
        if event_record:
            records.append(event_record)
            record_id += 1
    
    # Also parse general sections (non-event specific knowledge)
    general_sections = parse_general_sections(content, record_id)
    records.extend(general_sections)
    
    return records

def parse_event_details(event_name, event_content, record_id):
    """Parse detailed event information into structured record"""
    
    # Extract key information patterns
    context_match = re.search(r'- \*\*Context\*\*:\s*(.*?)(?=\n-|\n\*\*|\Z)', event_content, re.DOTALL)
    properties_match = re.search(r'- \*\*Properties\*\*:\s*(.*?)(?=\n-|\n\*\*|\Z)', event_content, re.DOTALL)
    implementation_match = re.search(r'- \*\*Implementation\*\*:\s*(.*?)(?=\n-|\n\*\*|\Z)', event_content, re.DOTALL)
    timing_match = re.search(r'- \*\*Timing\*\*:\s*(.*?)(?=\n-|\n\*\*|\Z)', event_content, re.DOTALL)
    screen_match = re.search(r'- \*\*Screen\*\*:\s*(.*?)(?=\n-|\n\*\*|\Z)', event_content, re.DOTALL)
    debug_match = re.search(r'- \*\*Debug Usage\*\*:\s*(.*?)(?=\n-|\n\*\*|\Z)', event_content, re.DOTALL)
    examples_match = re.search(r'- \*\*Production Examples\*\*:\s*(.*?)(?=\n-|\n\*\*|\Z)', event_content, re.DOTALL)
    user_journey_match = re.search(r'- \*\*User Journey\*\*:\s*(.*?)(?=\n-|\n\*\*|\Z)', event_content, re.DOTALL)
    
    # Build comprehensive description
    description_parts = [f"Event: {event_name}"]
    
    if context_match:
        context = context_match.group(1).strip().replace('\n', ' ')
        description_parts.append(f"Context: {context}")
    
    if timing_match:
        timing = timing_match.group(1).strip().replace('\n', ' ')
        description_parts.append(f"Timing: {timing}")
    
    if screen_match:
        screen = screen_match.group(1).strip().replace('\n', ' ')
        description_parts.append(f"Screen: {screen}")
    
    if user_journey_match:
        journey = user_journey_match.group(1).strip().replace('\n', ' ')
        description_parts.append(f"User Journey: {journey}")
    
    if debug_match:
        debug = debug_match.group(1).strip().replace('\n', ' ')
        description_parts.append(f"Debug Usage: {debug}")
    
    # Extract properties for structured data
    properties = {}
    if properties_match:
        props_text = properties_match.group(1).strip()
        # Parse property lines
        prop_lines = [line.strip() for line in props_text.split('\n') if line.strip() and not line.strip().startswith('-')]
        for line in prop_lines:
            if ':' in line:
                key, value = line.split(':', 1)
                properties[key.strip().replace('`', '')] = value.strip()
    
    # Create searchable description
    full_description = '. '.join(description_parts)
    
    # Add examples for better searchability
    if examples_match:
        examples = examples_match.group(1).strip().replace('\n', ' ')
        full_description += f". Production Examples: {examples}"
    
    return {
        "id": f"event_{record_id}",
        "event_name": event_name,
        "description": full_description,
        "context": context_match.group(1).strip() if context_match else "",
        "properties": properties,
        "implementation": implementation_match.group(1).strip() if implementation_match else "",
        "timing": timing_match.group(1).strip() if timing_match else "",
        "screen": screen_match.group(1).strip() if screen_match else "",
        "debug_usage": debug_match.group(1).strip() if debug_match else "",
        "examples": examples_match.group(1).strip() if examples_match else "",
        "user_journey": user_journey_match.group(1).strip() if user_journey_match else "",
        "type": "event_knowledge",
        "full_content": event_content
    }

def parse_general_sections(content, start_id):
    """Parse general analytics knowledge sections"""
    records = []
    
    # Parse overview section
    overview_match = re.search(r'## Overview\n(.*?)(?=##|\Z)', content, re.DOTALL)
    if overview_match:
        overview_content = overview_match.group(1).strip()
        records.append({
            "id": f"general_{start_id}",
            "title": "Analytics Overview",
            "description": f"Analytics Knowledge Base Overview: {overview_content}",
            "content": overview_content,
            "type": "general_knowledge"
        })
        start_id += 1
    
    # Parse category sections (### patterns)
    category_pattern = r'### (\d+\.\s+.*?)\n(.*?)(?=###|\Z)'
    category_matches = re.findall(category_pattern, content, re.DOTALL)
    
    for category_title, category_content in category_matches:
        if category_content.strip():
            records.append({
                "id": f"category_{start_id}",
                "title": category_title.strip(),
                "description": f"Analytics Category: {category_title.strip()}. {category_content[:300]}...",
                "content": category_content.strip(),
                "type": "category_knowledge"
            })
            start_id += 1
    
    return records

# ---------------------------------------------------------------------------
# Load and parse analytics knowledge
# ---------------------------------------------------------------------------
print(f"📖 Parsing comprehensive analytics knowledge from {KNOWLEDGE_PATH}...")
records = parse_analytics_knowledge(KNOWLEDGE_PATH)
print(f"✅ Parsed {len(records)} analytics knowledge entries")

# Show breakdown by type
event_count = len([r for r in records if r['type'] == 'event_knowledge'])
general_count = len([r for r in records if r['type'] == 'general_knowledge'])
category_count = len([r for r in records if r['type'] == 'category_knowledge'])

print(f"   📊 Events: {event_count}")
print(f"   📋 General: {general_count}")
print(f"   🗂️ Categories: {category_count}")

# ---------------------------------------------------------------------------
# Embed descriptions
# ---------------------------------------------------------------------------
print("🧠 Generating embeddings for analytics knowledge...")
emb_model = OpenAIEmbeddings(
    api_key=OPENAI_KEY,
    model="text-embedding-3-small",
    dimensions=DIMENSIONS,
    http_client=httpx.Client(verify=False, timeout=30),
)

vectors = []
for i, rec in enumerate(records):
    # Use description for embedding
    embedding_text = rec["description"]
    
    try:
        embedding = emb_model.embed_query(embedding_text)
        
        # Create vector tuple (id, embedding, metadata)
        vector_tuple = (
            rec["id"],
            embedding,
            rec  # All record data as metadata
        )
        vectors.append(vector_tuple)
        
        if (i + 1) % 50 == 0:
            print(f"   🔄 Generated {i + 1}/{len(records)} embeddings...")
    
    except Exception as e:
        print(f"   ❌ Error embedding record {rec['id']}: {e}")

print(f"✅ Generated {len(vectors)} embeddings successfully")

# ---------------------------------------------------------------------------
# Upsert into Pinecone
# ---------------------------------------------------------------------------
print("🚀 Connecting to Pinecone...")
pc = Pinecone(api_key=PINECONE_KEY, ssl_verify=False)

# Check if index exists, create if not
if INDEX_NAME not in [i.name for i in pc.list_indexes()]:
    print(f"📊 Creating Pinecone index '{INDEX_NAME}'...")
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
    print(f"   ✅ Created index '{INDEX_NAME}'")

index = pc.Index(INDEX_NAME)

# Upsert in batches for better performance
batch_size = 100
total_batches = (len(vectors) + batch_size - 1) // batch_size

for i in range(0, len(vectors), batch_size):
    batch = vectors[i:i + batch_size]
    batch_num = i // batch_size + 1
    
    # Clean metadata for Pinecone compatibility
    cleaned_batch = []
    for vector_id, embedding, metadata in batch:
        # Convert dict properties to string
        if 'properties' in metadata and isinstance(metadata['properties'], dict):
            metadata['properties'] = json.dumps(metadata['properties'])
        cleaned_batch.append((vector_id, embedding, metadata))
    
    try:
        index.upsert(cleaned_batch)
        print(f"📤 Upserted batch {batch_num}/{total_batches} ({len(cleaned_batch)} vectors)")
    except Exception as e:
        print(f"❌ Error upserting batch {batch_num}: {e}")

print(f"✅ Successfully upserted {len(vectors)} analytics knowledge entries to '{INDEX_NAME}' index!")
print(f"🎯 Index now contains:")
print(f"   📊 {event_count} detailed event descriptions with context, timing, and debug info")
print(f"   📋 {general_count} general analytics knowledge sections")
print(f"   🗂️ {category_count} categorized analytics insights")
print(f"   🔍 Ready for semantic search in mixpanel_user_activity chat interface!") 