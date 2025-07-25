#!/usr/bin/env python3
"""
🚀 COMPREHENSIVE Analytics Knowledge Ingestion - 1536D Vector Database
Ingest ALL analytics knowledge including events, properties, patterns, user journeys, and business intelligence
Creates comprehensive 1536D vector database for premium analytics intelligence
"""

import os
import httpx
import json
import re
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec
import sys
from typing import List, Dict

# ---------------------------------------------------------------------------
# Disable SSL verification globally
# ---------------------------------------------------------------------------
from network_utils import install_insecure_ssl
install_insecure_ssl()

# ---------------------------------------------------------------------------
# 🚀 PREMIUM CONFIGURATION
# ---------------------------------------------------------------------------
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT", "aws-us-east-1")

# Premium configuration - 1536D with text-embedding-3-large
DIMENSIONS = 1536
EMBEDDING_MODEL = "text-embedding-3-large"
INDEX_NAME = "analytics-event-knowledge-1536"
KNOWLEDGE_BASE_PATH = "resources/analytics_events_knowledge_base.txt"

def main():
    """Main function to ingest comprehensive analytics knowledge with 1536D vectors"""
    print("🚀 COMPREHENSIVE Analytics Knowledge Ingestion - 1536D Vector Database")
    print(f"📊 Configuration: {EMBEDDING_MODEL} with {DIMENSIONS} dimensions")
    print("🎯 Ingesting: Events + Properties + Patterns + User Journeys + Business Intelligence")
    
    # Validate configuration
    if not OPENAI_KEY:
        print("❌ OPENAI_API_KEY missing in environment")
        sys.exit(1)
    if not PINECONE_KEY:
        print("❌ PINECONE_API_KEY missing in environment")
        sys.exit(1)
    
    # Check if knowledge base file exists
    if not os.path.exists(KNOWLEDGE_BASE_PATH):
        print(f"❌ Knowledge base file not found at {KNOWLEDGE_BASE_PATH}")
        sys.exit(1)
    
    print(f"✅ Found knowledge base: {KNOWLEDGE_BASE_PATH}")
    
    # ---------------------------------------------------------------------------
    # Parse COMPREHENSIVE Analytics Knowledge Base
    # ---------------------------------------------------------------------------
    print("📖 Parsing comprehensive analytics knowledge base...")
    try:
        with open(KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"✅ Loaded knowledge base: {len(content):,} characters")
        
        # Parse ALL content types from the knowledge base
        all_knowledge_data = parse_comprehensive_analytics_knowledge(content)
        print(f"✅ Parsed {len(all_knowledge_data)} knowledge records from analytics base")
        
        # Show sample by type
        if all_knowledge_data:
            types_summary = {}
            for record in all_knowledge_data:
                record_type = record.get('type', 'unknown')
                types_summary[record_type] = types_summary.get(record_type, 0) + 1
            
            print("\n📋 Knowledge Types Parsed:")
            for record_type, count in types_summary.items():
                print(f"  • {record_type.replace('_', ' ').title()}: {count} records")
    
    except Exception as e:
        print(f"❌ Error reading knowledge base: {e}")
        sys.exit(1)
    
    if not all_knowledge_data:
        print("❌ No valid knowledge records found in knowledge base")
        sys.exit(1)
    
    # ---------------------------------------------------------------------------
    # 🚀 Initialize Premium OpenAI Embeddings (1536D)
    # ---------------------------------------------------------------------------
    print(f"🧠 Initializing premium embeddings ({EMBEDDING_MODEL})...")
    try:
        emb_model = OpenAIEmbeddings(
            api_key=OPENAI_KEY,
            model=EMBEDDING_MODEL,
            dimensions=DIMENSIONS,
            http_client=httpx.Client(verify=False, timeout=60),
        )
        print(f"✅ Premium embedding model initialized: {EMBEDDING_MODEL} ({DIMENSIONS}D)")
    except Exception as e:
        print(f"❌ Error initializing premium embeddings: {e}")
        sys.exit(1)
    
    # ---------------------------------------------------------------------------
    # Generate Premium 1536D Embeddings for ALL Knowledge
    # ---------------------------------------------------------------------------
    print("🔢 Generating premium 1536D embeddings for comprehensive knowledge...")
    vectors = []
    successful_embeddings = 0
    failed_embeddings = 0
    
    try:
        for i, record in enumerate(all_knowledge_data):
            try:
                # Use comprehensive searchable content for embedding
                embedding_text = record.get("searchable_content", "")
                
                if not embedding_text:
                    print(f"⚠️ Skipping record {i} - no searchable content")
                    continue
                
                # Generate premium 1536D embedding
                embedding = emb_model.embed_query(embedding_text)
                
                # Create vector tuple with comprehensive metadata
                vector_tuple = (
                    record["id"],
                    embedding,
                    record  # All record data as metadata
                )
                vectors.append(vector_tuple)
                successful_embeddings += 1
                
                if (i + 1) % 25 == 0:
                    print(f"   🔄 Generated {i + 1}/{len(all_knowledge_data)} premium embeddings...")
            
            except Exception as e:
                print(f"   ❌ Error embedding record {record['id']}: {e}")
                failed_embeddings += 1
        
        print(f"✅ COMPREHENSIVE EMBEDDINGS COMPLETE:")
        print(f"   📈 Successful: {successful_embeddings}")
        print(f"   ❌ Failed: {failed_embeddings}")
        print(f"   🎯 Success Rate: {(successful_embeddings/len(all_knowledge_data)*100):.1f}%")
    
    except Exception as e:
        print(f"❌ Error generating comprehensive embeddings: {e}")
        sys.exit(1)
    
    # ---------------------------------------------------------------------------
    # 🚀 Premium Pinecone Setup (1536D Index) - Replace existing
    # ---------------------------------------------------------------------------
    print("🚀 COMPREHENSIVE PINECONE SETUP: Replacing with enhanced 1536D configuration...")
    try:
        pc = Pinecone(api_key=PINECONE_KEY, ssl_verify=False)
        
        # Check if index exists
        existing_indexes = [index.name for index in pc.list_indexes()]
        
        if INDEX_NAME in existing_indexes:
            print(f"🔄 Deleting existing index to rebuild with comprehensive knowledge: {INDEX_NAME}")
            pc.delete_index(INDEX_NAME)
            import time
            time.sleep(10)  # Wait for deletion to complete
        
        print(f"📦 Creating comprehensive Pinecone index: {INDEX_NAME} ({DIMENSIONS}D)")
        
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
            dimension=DIMENSIONS,  # 1536D
            metric="cosine",
            spec=ServerlessSpec(cloud=cloud, region=region),
        )
        print(f"✅ Created comprehensive index: {INDEX_NAME} ({DIMENSIONS}D)")
        
        # Wait for index to be ready
        import time
        time.sleep(30)
        
        # Get index reference
        index = pc.Index(INDEX_NAME)
        
    except Exception as e:
        print(f"❌ Error connecting to Pinecone: {e}")
        sys.exit(1)
    
    # ---------------------------------------------------------------------------
    # 🚀 Upsert Comprehensive Vectors to Pinecone
    # ---------------------------------------------------------------------------
    print("📤 Upserting comprehensive analytics knowledge to Pinecone...")
    try:
        # Upsert in batches of 50 (smaller batches for premium embeddings)
        batch_size = 50
        total_upserted = 0
        
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            index.upsert(batch)
            total_upserted += len(batch)
            print(f"  📊 Upserted {total_upserted}/{len(vectors)} comprehensive vectors")
        
        print(f"✅ Successfully upserted {len(vectors)} comprehensive vectors to {INDEX_NAME}")
        
        # Verify the upsert
        import time
        time.sleep(5)  # Allow time for indexing
        stats = index.describe_index_stats()
        print(f"📊 Final index stats: {stats['total_vector_count']} total vectors")
        
    except Exception as e:
        print(f"❌ Error upserting to Pinecone: {e}")
        sys.exit(1)
    
    print("\n🎉 COMPREHENSIVE ANALYTICS KNOWLEDGE INGESTION COMPLETED!")
    print(f"📋 Total knowledge records processed: {len(all_knowledge_data)}")
    print(f"🗄️  Index: {INDEX_NAME}")
    print(f"🧠 Premium model: {EMBEDDING_MODEL} ({DIMENSIONS}D)")
    print(f"📈 Success rate: {(successful_embeddings/len(all_knowledge_data)*100):.1f}%")
    print("\n💡 Your analytics system now has COMPREHENSIVE 1536D vector intelligence!")
    print("🚀 Enhanced with events, properties, patterns, user journeys, and business intelligence!")


def parse_comprehensive_analytics_knowledge(content: str) -> List[Dict]:
    """
    Parse the analytics knowledge base file and extract ALL types of analytics knowledge
    Including: Events, Properties, Patterns, User Journeys, Business Intelligence
    """
    all_knowledge = []
    lines = content.split('\n')
    
    print(f"📋 Parsing {len(lines)} lines for comprehensive analytics knowledge...")
    
    i = 0
    knowledge_counter = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines and very short content
        if not line or len(line) < 5:
            i += 1
            continue
        
        # 1. PARSE INDIVIDUAL EVENTS (#### **event_name**)
        event_match = re.match(r'####\s*\*\*([^*]+)\*\*', line)
        if event_match:
            event_knowledge = parse_event_knowledge(lines, i, knowledge_counter)
            if event_knowledge:
                all_knowledge.append(event_knowledge)
                knowledge_counter += 1
            i += 1
            continue
        
        # 2. PARSE MAJOR SECTIONS (## Section Name)
        major_section_match = re.match(r'##\s+(.+)', line)
        if major_section_match:
            section_knowledge = parse_section_knowledge(lines, i, knowledge_counter)
            if section_knowledge:
                all_knowledge.append(section_knowledge)
                knowledge_counter += 1
            i += 1
            continue
        
        # 3. PARSE SUBSECTIONS (### Subsection Name)
        subsection_match = re.match(r'###\s+(.+)', line)
        if subsection_match:
            subsection_knowledge = parse_subsection_knowledge(lines, i, knowledge_counter)
            if subsection_knowledge:
                all_knowledge.append(subsection_knowledge)
                knowledge_counter += 1
            i += 1
            continue
        
        # 4. PARSE PROPERTY ANALYSIS PATTERNS
        if 'properties' in line.lower() and ('analysis' in line.lower() or 'correlation' in line.lower()):
            property_knowledge = parse_property_knowledge(lines, i, knowledge_counter)
            if property_knowledge:
                all_knowledge.append(property_knowledge)
                knowledge_counter += 1
            i += 1
            continue
        
        # 5. PARSE USER JOURNEY PATTERNS
        if any(pattern in line.lower() for pattern in ['flow pattern', 'journey', 'user flow', 'navigation pattern']):
            journey_knowledge = parse_journey_knowledge(lines, i, knowledge_counter)
            if journey_knowledge:
                all_knowledge.append(journey_knowledge)
                knowledge_counter += 1
            i += 1
            continue
        
        i += 1
    
    print(f"✅ Comprehensive parsing complete: {len(all_knowledge)} knowledge records extracted")
    return all_knowledge


def parse_event_knowledge(lines: List[str], start_idx: int, counter: int) -> Dict:
    """Parse individual event knowledge"""
    try:
        event_line = lines[start_idx].strip()
        event_match = re.match(r'####\s*\*\*([^*]+)\*\*', event_line)
        if not event_match:
            return None
        
        event_name = event_match.group(1).strip()
        
        # Parse event details
        event_data = {
            'id': f"event_{counter:03d}_{clean_for_id(event_name)}",
            'type': 'analytics_event',
            'name': event_name,
            'event_name': event_name,
            'context': '',
            'properties': '',
            'timing': '',
            'screen': '',
            'user_journey': '',
            'user_state': '',
            'debug_usage': '',
            'examples': '',
            'implementation': '',
            'event_category': get_event_category(event_name),
            'full_content': f"Event: {event_name}"
        }
        
        # Parse next lines for event details
        content_parts = [f"Event: {event_name}"]
        for j in range(start_idx + 1, min(start_idx + 30, len(lines))):
            detail_line = lines[j].strip()
            
            if detail_line.startswith('#### **'):  # Next event
                break
                
            if not detail_line:
                continue
                
            content_parts.append(detail_line)
            
            # Parse specific fields
            if detail_line.startswith('- **Context**:'):
                event_data['context'] = detail_line.replace('- **Context**:', '').strip()
            elif detail_line.startswith('- **Properties**:'):
                event_data['properties'] = detail_line.replace('- **Properties**:', '').strip()
            elif detail_line.startswith('- **Timing**:'):
                event_data['timing'] = detail_line.replace('- **Timing**:', '').strip()
            elif detail_line.startswith('- **Screen**:'):
                event_data['screen'] = detail_line.replace('- **Screen**:', '').strip()
            elif detail_line.startswith('- **User Journey**:'):
                event_data['user_journey'] = detail_line.replace('- **User Journey**:', '').strip()
            elif detail_line.startswith('- **User State**:'):
                event_data['user_state'] = detail_line.replace('- **User State**:', '').strip()
            elif detail_line.startswith('- **Debug Usage**:'):
                event_data['debug_usage'] = detail_line.replace('- **Debug Usage**:', '').strip()
            elif detail_line.startswith('- **Implementation**:'):
                event_data['implementation'] = detail_line.replace('- **Implementation**:', '').strip()
            elif detail_line.startswith('- **Production Example'):
                event_data['examples'] = detail_line.replace('- **Production Examples**:', '').replace('- **Examples**:', '').strip()
        
        event_data['full_content'] = ' '.join(content_parts)
        event_data['searchable_content'] = event_data['full_content']
        event_data['description'] = event_data['context'] if event_data['context'] else f"Analytics event: {event_name}"
        
        return event_data
        
    except Exception as e:
        print(f"❌ Error parsing event at line {start_idx}: {e}")
        return None


def parse_section_knowledge(lines: List[str], start_idx: int, counter: int) -> Dict:
    """Parse major section knowledge (## headers)"""
    try:
        section_line = lines[start_idx].strip()
        section_match = re.match(r'##\s+(.+)', section_line)
        if not section_match:
            return None
        
        section_name = section_match.group(1).strip()
        
        # Skip if it's just "Overview" or very short sections
        if section_name.lower() in ['overview'] or len(section_name) < 5:
            return None
        
        # Clean section name for ASCII-only ID
        clean_section_name = clean_for_id(section_name)
        
        section_data = {
            'id': f"section_{counter:03d}_{clean_section_name}",
            'type': 'analytics_section',
            'name': section_name,
            'section_type': 'major_section',
            'content_type': determine_content_type(section_name),
            'full_content': f"Section: {section_name}"
        }
        
        # Parse section content
        content_parts = [f"Section: {section_name}"]
        for j in range(start_idx + 1, min(start_idx + 100, len(lines))):
            if j >= len(lines):
                break
                
            content_line = lines[j].strip()
            
            # Stop at next major section
            if content_line.startswith('## '):
                break
                
            if content_line and len(content_line) > 10:
                content_parts.append(content_line)
        
        section_data['full_content'] = ' '.join(content_parts)
        section_data['searchable_content'] = section_data['full_content']
        section_data['description'] = f"Analytics section: {section_name}"
        
        return section_data
        
    except Exception as e:
        print(f"❌ Error parsing section at line {start_idx}: {e}")
        return None


def parse_subsection_knowledge(lines: List[str], start_idx: int, counter: int) -> Dict:
    """Parse subsection knowledge (### headers)"""
    try:
        subsection_line = lines[start_idx].strip()
        subsection_match = re.match(r'###\s+(.+)', subsection_line)
        if not subsection_match:
            return None
        
        subsection_name = subsection_match.group(1).strip()
        
        # Clean subsection name for ASCII-only ID
        clean_subsection_name = clean_for_id(subsection_name)[:30]
        
        subsection_data = {
            'id': f"subsection_{counter:03d}_{clean_subsection_name}",
            'type': 'analytics_subsection',
            'name': subsection_name,
            'section_type': 'subsection',
            'content_type': determine_content_type(subsection_name),
            'full_content': f"Subsection: {subsection_name}"
        }
        
        # Parse subsection content
        content_parts = [f"Subsection: {subsection_name}"]
        for j in range(start_idx + 1, min(start_idx + 50, len(lines))):
            if j >= len(lines):
                break
                
            content_line = lines[j].strip()
            
            # Stop at next section/subsection
            if content_line.startswith('## ') or content_line.startswith('### '):
                break
                
            if content_line and len(content_line) > 5:
                content_parts.append(content_line)
        
        subsection_data['full_content'] = ' '.join(content_parts)
        subsection_data['searchable_content'] = subsection_data['full_content']
        subsection_data['description'] = f"Analytics subsection: {subsection_name}"
        
        return subsection_data
        
    except Exception as e:
        print(f"❌ Error parsing subsection at line {start_idx}: {e}")
        return None


def parse_property_knowledge(lines: List[str], start_idx: int, counter: int) -> Dict:
    """Parse property analysis and correlation knowledge"""
    try:
        property_line = lines[start_idx].strip()
        
        property_data = {
            'id': f"property_{counter:03d}_analysis",
            'type': 'property_analysis',
            'name': f"Property Analysis: {property_line[:50]}",
            'analysis_type': 'property_correlation',
            'content_type': 'property_insights',
            'full_content': property_line
        }
        
        # Parse property content
        content_parts = [property_line]
        for j in range(start_idx + 1, min(start_idx + 20, len(lines))):
            if j >= len(lines):
                break
                
            content_line = lines[j].strip()
            
            if content_line.startswith('##') or content_line.startswith('###'):
                break
                
            if content_line:
                content_parts.append(content_line)
        
        property_data['full_content'] = ' '.join(content_parts)
        property_data['searchable_content'] = property_data['full_content']
        property_data['description'] = f"Property analysis and correlation insights"
        
        return property_data
        
    except Exception as e:
        return None


def parse_journey_knowledge(lines: List[str], start_idx: int, counter: int) -> Dict:
    """Parse user journey and flow pattern knowledge"""
    try:
        journey_line = lines[start_idx].strip()
        
        journey_data = {
            'id': f"journey_{counter:03d}_pattern",
            'type': 'user_journey_pattern',
            'name': f"User Journey: {journey_line[:50]}",
            'pattern_type': 'user_flow',
            'content_type': 'journey_insights',
            'full_content': journey_line
        }
        
        # Parse journey content
        content_parts = [journey_line]
        for j in range(start_idx + 1, min(start_idx + 30, len(lines))):
            if j >= len(lines):
                break
                
            content_line = lines[j].strip()
            
            if content_line.startswith('##') or content_line.startswith('###'):
                break
                
            if content_line:
                content_parts.append(content_line)
        
        journey_data['full_content'] = ' '.join(content_parts)
        journey_data['searchable_content'] = journey_data['full_content']
        journey_data['description'] = f"User journey pattern and flow analysis"
        
        return journey_data
        
    except Exception as e:
        return None


def determine_content_type(name: str) -> str:
    """Determine the type of analytics content"""
    name_lower = name.lower()
    
    if any(term in name_lower for term in ['properties', 'property']):
        return 'property_analysis'
    elif any(term in name_lower for term in ['journey', 'flow', 'pattern']):
        return 'user_journey'
    elif any(term in name_lower for term in ['business', 'intelligence', 'conversion']):
        return 'business_intelligence'
    elif any(term in name_lower for term in ['error', 'failure', 'debug']):
        return 'error_analysis'
    elif any(term in name_lower for term in ['sequence', 'timing', 'performance']):
        return 'performance_analysis'
    else:
        return 'general_analytics'


def clean_for_id(text: str) -> str:
    """Clean text to be ASCII-only for Pinecone vector IDs"""
    import re
    
    # Remove emojis and non-ASCII characters
    ascii_text = ''.join(char for char in text if ord(char) < 128)
    
    # Replace spaces and special characters with underscores
    clean_text = re.sub(r'[^a-zA-Z0-9_-]', '_', ascii_text)
    
    # Remove multiple consecutive underscores
    clean_text = re.sub(r'_+', '_', clean_text)
    
    # Remove leading/trailing underscores
    clean_text = clean_text.strip('_').lower()
    
    return clean_text if clean_text else 'unknown'


def get_event_category(event_name: str) -> str:
    """Get event category based on event name"""
    event_lower = event_name.lower()
    
    if any(term in event_lower for term in ['app_open', 'app_closed', 'session', 'timer']):
        return 'app_lifecycle'
    elif any(term in event_lower for term in ['auth', 'login', 'otp', 'pin', 'biometric', 'mpin']):
        return 'authentication'
    elif any(term in event_lower for term in ['page', 'screen', 'navigate', 'nav_bar', 'land']):
        return 'navigation'
    elif any(term in event_lower for term in ['upi', 'pay', 'transaction', 'money', 'amount']):
        return 'payments'
    elif any(term in event_lower for term in ['borrow', 'loan', 'lend', 'credit', 'repay']):
        return 'lending'
    elif any(term in event_lower for term in ['account', 'bank', 'balance', 'sa_', 'savings']):
        return 'banking'
    elif any(term in event_lower for term in ['help', 'support', 'faq', 'chat', 'chatbot']):
        return 'support'
    elif any(term in event_lower for term in ['error', 'exception', 'fail', 'timeout']):
        return 'errors'
    elif any(term in event_lower for term in ['sync', 'fetch', 'api', 'data']):
        return 'data_management'
    else:
        return 'general'


if __name__ == "__main__":
    main() 