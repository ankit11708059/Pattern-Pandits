#!/usr/bin/env python3
"""
Simplified parser test to debug the issue
"""
import re

def simple_parse_test():
    """Test the parsing logic step by step"""
    
    print("🔍 Testing simplified parsing...")
    
    # Read the file
    with open('resources/analytics_events_knowledge_base.txt', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"✅ File read: {len(content):,} characters")
    
    lines = content.split('\n')
    print(f"✅ Split into {len(lines):,} lines")
    
    # Find all #### lines
    event_lines = []
    for i, line in enumerate(lines):
        original_line = line
        line = line.strip()
        
        if line.startswith('####'):
            event_lines.append((i+1, original_line, line))
    
    print(f"✅ Found {len(event_lines)} lines starting with ####")
    
    # Test regex on each
    pattern = r'####\s*\*\*([^*]+)\*\*'
    matched_events = []
    
    for line_num, original, stripped in event_lines[:10]:  # Test first 10
        print(f"\nLine {line_num}: '{stripped}'")
        match = re.match(pattern, stripped)
        if match:
            event_name = match.group(1).strip()
            matched_events.append((line_num, event_name))
            print(f"  ✅ MATCHED: '{event_name}'")
        else:
            print(f"  ❌ NO MATCH")
    
    print(f"\n📊 Summary: {len(matched_events)} events matched out of {len(event_lines)} #### lines")
    
    return matched_events

if __name__ == "__main__":
    matches = simple_parse_test() 