#!/usr/bin/env python3
"""
User Flow Analyzer - Command Line Interface
Analyze user event sequences to understand behavioral patterns
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import os
from collections import defaultdict, Counter
from dotenv import load_dotenv
from typing import Dict, List, Tuple, Optional
import argparse
import sys
from network_utils import install_insecure_ssl

# Disable SSL verification
install_insecure_ssl()

# Load environment variables
load_dotenv()

# Mixpanel API configuration
MIXPANEL_PROJECT_ID = os.getenv("MIXPANEL_PROJECT_ID")
MIXPANEL_USERNAME = os.getenv("MIXPANEL_USERNAME")
MIXPANEL_SECRET = os.getenv("MIXPANEL_SECRET")

# Flow knowledge storage
FLOW_KNOWLEDGE_FILE = "user_flow_knowledge.txt"

class UserFlowAnalyzer:
    def __init__(self):
        self.base_url = "https://in.mixpanel.com/api"  # India cluster
        self.project_id = MIXPANEL_PROJECT_ID
        self.username = MIXPANEL_USERNAME
        self.secret = MIXPANEL_SECRET
        self.auth_header = self._get_auth_header()
        
    def _get_auth_header(self):
        """Create authentication header for Mixpanel API"""
        return (self.username, self.secret)
    
    def fetch_user_events(self, user_id: str, days_back: int = 30) -> List[Dict]:
        """
        Fetch events for a specific user from Mixpanel using the provided ID directly as distinct_id
        """
        # Use the provided ID directly as distinct_id
        distinct_id = user_id
        print(f"🔑 Using distinct_id: {distinct_id}")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Format dates for Mixpanel API
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        # Use the stream query API
        params = {
            "project_id": self.project_id,
            "distinct_ids": json.dumps([distinct_id]),
            "from_date": start_date_str,
            "to_date": end_date_str
        }
        
        try:
            url = f"{self.base_url}/query/stream/query"
            
            response = requests.get(
                url,
                params=params,
                auth=self.auth_header,
                headers={'accept': 'application/json'},
                verify=False,
                timeout=30
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    events = []
                    
                    # Extract events from the response structure
                    if isinstance(data, dict) and "results" in data:
                        results = data["results"]
                        if isinstance(results, dict):
                            for user_id, user_events in results.items():
                                if isinstance(user_events, list):
                                    events.extend(user_events)
                        elif isinstance(results, list):
                            events.extend(results)
                    
                    return events
                except json.JSONDecodeError as e:
                    print(f"❌ Failed to parse API response: {e}")
                    return []
            else:
                print(f"❌ Mixpanel API error: {response.status_code}")
                if response.text:
                    print(f"Error details: {response.text[:200]}")
                return []
                
        except Exception as e:
            print(f"❌ Error fetching user events: {e}")
            return []
    
    def analyze_event_sequence(self, events: List[Dict]) -> Dict:
        """
        Analyze chronological event sequence to understand user flow with properties
        """
        if not events:
            return {}
        
        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda x: x.get('properties', {}).get('time', 0))
        
        # Extract event sequence with timing and properties
        event_sequence = []
        event_transitions = defaultdict(int)
        event_timings = defaultdict(list)
        property_transitions = defaultdict(lambda: defaultdict(list))
        event_property_patterns = defaultdict(lambda: defaultdict(set))
        
        for i, event in enumerate(sorted_events):
            event_name = event.get('event', 'unknown_event')
            timestamp = event.get('properties', {}).get('time', 0)
            properties = event.get('properties', {})
            
            # Convert timestamp to readable time
            try:
                event_time = datetime.fromtimestamp(timestamp)
            except (ValueError, TypeError):
                event_time = datetime.now()
            
            # Extract ALL properties (minimal filtering)
            relevant_props = {}
            for key, value in properties.items():
                if key not in ['mp_lib', 'token', '$insert_id']:
                    if isinstance(value, (str, int, float, bool, list, dict)):
                        if isinstance(value, (list, dict)):
                            relevant_props[key] = str(value)
                        else:
                            relevant_props[key] = value
                        event_property_patterns[event_name][key].add(str(value))
            
            event_info = {
                'event': event_name,
                'timestamp': timestamp,
                'time': event_time,
                'properties': properties,
                'relevant_properties': relevant_props
            }
            event_sequence.append(event_info)
            
            # Track transitions with properties context
            if i < len(sorted_events) - 1:
                next_event = sorted_events[i + 1].get('event', 'unknown_event')
                next_properties = sorted_events[i + 1].get('properties', {})
                
                next_relevant_props = {}
                for key, value in next_properties.items():
                    if key not in ['mp_lib', 'token', '$insert_id']:
                        if isinstance(value, (str, int, float, bool, list, dict)):
                            if isinstance(value, (list, dict)):
                                next_relevant_props[key] = str(value)
                            else:
                                next_relevant_props[key] = value
                
                transition_key = f"{event_name} → {next_event}"
                event_transitions[transition_key] += 1
                
                property_transitions[transition_key]['from_properties'].append(relevant_props)
                property_transitions[transition_key]['to_properties'].append(next_relevant_props)
                
                # Calculate time difference
                next_timestamp = sorted_events[i + 1].get('properties', {}).get('time', timestamp)
                time_diff = next_timestamp - timestamp
                event_timings[transition_key].append(time_diff)
        
        # Calculate timing statistics
        timing_stats = {}
        for transition, times in event_timings.items():
            if times:
                timing_stats[transition] = {
                    'avg_seconds': sum(times) / len(times),
                    'min_seconds': min(times),
                    'max_seconds': max(times),
                    'count': len(times)
                }
        
        # Convert property patterns to readable format
        property_patterns = {}
        for event_name, props in event_property_patterns.items():
            property_patterns[event_name] = {}
            for prop_name, values in props.items():
                property_patterns[event_name][prop_name] = list(values)
        
        return {
            'sequence': event_sequence,
            'transitions': dict(event_transitions),
            'timing_stats': timing_stats,
            'property_transitions': dict(property_transitions),
            'property_patterns': property_patterns,
            'total_events': len(events),
            'unique_events': len(set(event.get('event') for event in events)),
            'session_duration': (sorted_events[-1].get('properties', {}).get('time', 0) - 
                               sorted_events[0].get('properties', {}).get('time', 0)) if len(sorted_events) > 1 else 0
        }
    
    def generate_flow_insights(self, analysis: Dict) -> str:
        """
        Generate human-readable insights from flow analysis with properties
        """
        if not analysis:
            return "No flow analysis available."
        
        insights = []
        
        # Basic stats
        insights.append(f"📊 FLOW SUMMARY")
        insights.append(f"• Total Events: {analysis['total_events']}")
        insights.append(f"• Unique Event Types: {analysis['unique_events']}")
        insights.append(f"• Session Duration: {analysis['session_duration']:.0f} seconds ({analysis['session_duration']/60:.1f} minutes)")
        
        # Top transitions
        if analysis['transitions']:
            insights.append(f"\n🔄 MOST COMMON EVENT TRANSITIONS")
            top_transitions = sorted(analysis['transitions'].items(), key=lambda x: x[1], reverse=True)[:10]
            for transition, count in top_transitions:
                insights.append(f"• {transition}: {count} times")
        
        # Property patterns analysis
        if analysis.get('property_patterns'):
            insights.append(f"\n🏷️ PROPERTY PATTERNS (All Properties)")
            for event_name, props in list(analysis['property_patterns'].items())[:5]:  # Show first 5 events
                insights.append(f"• {event_name}:")
                for prop_name, values in list(props.items())[:10]:  # Show first 10 properties per event
                    if len(values) == 1:
                        insights.append(f"  - {prop_name}: {values[0]}")
                    elif len(values) <= 5:
                        insights.append(f"  - {prop_name}: {', '.join(values)}")
                    else:
                        insights.append(f"  - {prop_name}: {', '.join(values[:5])}... (and {len(values)-5} more values)")
        
        # Timing insights
        if analysis['timing_stats']:
            insights.append(f"\n⏱️ TIMING ANALYSIS")
            for transition, stats in list(analysis['timing_stats'].items())[:5]:
                avg_time = stats['avg_seconds']
                if avg_time < 60:
                    time_str = f"{avg_time:.1f} seconds"
                else:
                    time_str = f"{avg_time/60:.1f} minutes"
                insights.append(f"• {transition}: avg {time_str}")
        
        # Event sequence pattern
        if analysis['sequence']:
            insights.append(f"\n📋 EVENT FLOW PATTERN (First 10 events)")
            for i, event in enumerate(analysis['sequence'][:10]):
                insights.append(f"{i+1}. {event['event']} ({event['time'].strftime('%H:%M:%S')})")
            
            if len(analysis['sequence']) > 10:
                insights.append(f"... and {len(analysis['sequence']) - 10} more events")
        
        return "\n".join(insights)
    
    def save_flow_knowledge(self, user_id: str, analysis: Dict, insights: str):
        """
        Save discovered flow patterns with properties to knowledge file
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        knowledge_entry = f"""
================================================================================
📅 FLOW ANALYSIS - {timestamp}
🆔 Distinct ID: {user_id}
================================================================================

{insights}

🔗 DETAILED TRANSITIONS WITH PROPERTIES:
"""
        
        # Add detailed transition data with property context
        if analysis.get('transitions'):
            for transition, count in analysis['transitions'].items():
                knowledge_entry += f"\n{transition}: {count} occurrences"
                
                # Add timing if available
                if transition in analysis.get('timing_stats', {}):
                    stats = analysis['timing_stats'][transition]
                    knowledge_entry += f" (avg: {stats['avg_seconds']:.1f}s)"
                
                # Add property context for this transition
                if transition in analysis.get('property_transitions', {}):
                    prop_data = analysis['property_transitions'][transition]
                    if prop_data.get('from_properties'):
                        from_props = prop_data['from_properties']
                        to_props = prop_data['to_properties']
                        
                        if from_props:
                            sample_from = from_props[0] if from_props else {}
                            sample_to = to_props[0] if to_props else {}
                            
                            if sample_from or sample_to:
                                knowledge_entry += f"\n  📋 Property Context:"
                                if sample_from:
                                    knowledge_entry += f"\n    From: {sample_from}"
                                if sample_to:
                                    knowledge_entry += f"\n    To: {sample_to}"
        
        knowledge_entry += f"\n\n" + "="*80 + "\n"
        
        # Append to knowledge file
        try:
            with open(FLOW_KNOWLEDGE_FILE, 'a', encoding='utf-8') as f:
                f.write(knowledge_entry)
            print(f"✅ Flow knowledge saved to {FLOW_KNOWLEDGE_FILE}")
        except Exception as e:
            print(f"❌ Error saving flow knowledge: {e}")
    
    def load_flow_knowledge(self) -> str:
        """
        Load and display existing flow knowledge
        """
        try:
            if os.path.exists(FLOW_KNOWLEDGE_FILE):
                with open(FLOW_KNOWLEDGE_FILE, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                return "No flow knowledge file found. Start analyzing user flows to build knowledge!"
        except Exception as e:
            return f"Error loading flow knowledge: {e}"

    def save_events_to_file(self, user_id: str, events: List[Dict], days_back: int):
        """
        Save raw events data to a separate text file for each distinct_id
        """
        if not events:
            print("⚠️ No events to save")
            return
        
        # Create filename with distinct_id and timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_user_id = user_id[:16] + "..." if len(user_id) > 16 else user_id
        filename = f"events_{safe_user_id}_{days_back}d_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"📋 EVENTS DATA FOR DISTINCT_ID: {user_id}\n")
                f.write(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"📊 Total Events: {len(events)}\n")
                f.write(f"🗓️ Days Analyzed: {days_back}\n")
                f.write("=" * 80 + "\n\n")
                
                # Sort events by timestamp
                sorted_events = sorted(events, key=lambda x: x.get('properties', {}).get('time', 0))
                
                for i, event in enumerate(sorted_events, 1):
                    props = event.get('properties', {})
                    timestamp = props.get('time', 0)
                    
                    # Convert timestamp to readable time
                    try:
                        event_time = datetime.fromtimestamp(timestamp)
                        time_str = event_time.strftime('%Y-%m-%d %H:%M:%S')
                    except (ValueError, TypeError):
                        time_str = 'Unknown Time'
                    
                    # Write event header
                    f.write(f"EVENT #{i:03d} - {event.get('event', 'Unknown Event')}\n")
                    f.write(f"Time: {time_str}\n")
                    f.write(f"Timestamp: {timestamp}\n")
                    
                    # Write all properties (excluding system ones)
                    relevant_props = {}
                    for key, value in props.items():
                        if key not in ['mp_lib', 'token', '$insert_id']:
                            relevant_props[key] = value
                    
                    if relevant_props:
                        f.write("Properties:\n")
                        for key, value in relevant_props.items():
                            # Handle different value types
                            if isinstance(value, (list, dict)):
                                value_str = json.dumps(value, indent=2)
                            else:
                                value_str = str(value)
                            
                            # Truncate very long values
                            if len(value_str) > 200:
                                value_str = value_str[:200] + "..."
                            
                            f.write(f"  {key}: {value_str}\n")
                    else:
                        f.write("Properties: None\n")
                    
                    f.write("-" * 80 + "\n\n")
                
                # Add summary at the end
                f.write("=" * 80 + "\n")
                f.write("📊 SUMMARY\n")
                f.write("=" * 80 + "\n")
                
                # Count unique events
                unique_events = set(event.get('event', 'Unknown') for event in events)
                f.write(f"Total Events: {len(events)}\n")
                f.write(f"Unique Event Types: {len(unique_events)}\n")
                f.write(f"Date Range: {days_back} days\n")
                
                # Session duration
                if len(sorted_events) > 1:
                    start_time = sorted_events[0].get('properties', {}).get('time', 0)
                    end_time = sorted_events[-1].get('properties', {}).get('time', 0)
                    duration = end_time - start_time
                    f.write(f"Session Duration: {duration:.0f} seconds ({duration/60:.1f} minutes)\n")
                
                # List unique events
                f.write(f"\nUnique Event Types:\n")
                for event_type in sorted(unique_events):
                    count = sum(1 for e in events if e.get('event') == event_type)
                    f.write(f"  {event_type}: {count} occurrences\n")
            
            print(f"✅ Events saved to file: {filename}")
            return filename
            
        except Exception as e:
            print(f"❌ Error saving events to file: {e}")
            return None

def print_banner():
    """Print application banner"""
    print("=" * 60)
    print("🔄 USER FLOW ANALYZER - Command Line Interface")
    print("Analyze user event sequences and behavioral patterns")
    print("=" * 60)

def print_events_table(events: List[Dict], limit: int = 20):
    """Print events in a formatted table"""
    if not events:
        print("No events to display")
        return
    
    print(f"\n📋 EVENT SEQUENCE (showing first {min(limit, len(events))} of {len(events)} events)")
    print("-" * 80)
    print(f"{'#':<3} {'Event':<30} {'Time':<20} {'Props':<5}")
    print("-" * 80)
    
    for i, event in enumerate(events[:limit]):
        props = event.get('properties', {})
        timestamp = props.get('time', 0)
        
        try:
            time_str = datetime.fromtimestamp(timestamp).strftime('%m-%d %H:%M:%S') if timestamp else 'Unknown'
        except:
            time_str = 'Unknown'
        
        event_name = event.get('event', 'Unknown')[:29]
        prop_count = len([k for k in props.keys() if not k.startswith('$')])
        
        print(f"{i+1:<3} {event_name:<30} {time_str:<20} {prop_count:<5}")
    
    if len(events) > limit:
        print(f"... and {len(events) - limit} more events")
    print("-" * 80)

def interactive_mode(analyzer: UserFlowAnalyzer):
    """Run interactive mode for continuous analysis"""
    print("\n🚀 INTERACTIVE MODE - Enter 'quit' to exit")
    print("You can analyze multiple users without restarting the application")
    
    while True:
        print("\n" + "="*50)
        
        # Get user input
        user_id = input("🆔 Enter distinct ID (or 'quit' to exit): ").strip()
        if user_id.lower() in ['quit', 'exit', 'q']:
            print("👋 Goodbye!")
            break
        
        if not user_id:
            print("❌ Please enter a valid distinct ID")
            continue
        
        # Get days input
        try:
            days_input = input("📅 Days to analyze (default 30): ").strip()
            days_back = int(days_input) if days_input else 30
            if days_back < 1 or days_back > 365:
                print("❌ Days must be between 1 and 365")
                continue
        except ValueError:
            print("❌ Invalid number of days")
            continue
        
        # Auto-save option
        save_input = input("💾 Save to knowledge base? (y/N): ").strip().lower()
        auto_save = save_input in ['y', 'yes']
        
        # Events file save option
        save_events_input = input("📁 Save events to individual file? (Y/n): ").strip().lower()
        save_events_file = save_events_input not in ['n', 'no']
        
        print(f"\n🔍 Analyzing user {user_id} for the last {days_back} days...")
        
        # Fetch and analyze
        try:
            events = analyzer.fetch_user_events(user_id, days_back)
            
            if not events:
                print(f"⚠️ No events found for user {user_id} in the last {days_back} days")
                continue
            
            print(f"✅ Found {len(events)} events!")
            
            # Save events to individual file if requested
            if save_events_file:
                events_filename = analyzer.save_events_to_file(user_id, events, days_back)
            
            # Analyze sequence
            print("📊 Analyzing event sequence...")
            analysis = analyzer.analyze_event_sequence(events)
            
            if not analysis:
                print("❌ Could not analyze event sequence")
                continue
            
            # Generate insights
            insights = analyzer.generate_flow_insights(analysis)
            
            # Display results
            print("\n" + "="*60)
            print("📋 FLOW ANALYSIS RESULTS")
            print("="*60)
            print(insights)
            
            # Show events table
            show_events = input("\n🔍 Show event details? (y/N): ").strip().lower()
            if show_events in ['y', 'yes']:
                print_events_table(events)
            
            # Save analysis to knowledge base if requested
            if auto_save:
                analyzer.save_flow_knowledge(user_id, analysis, insights)
            
            print("\n✅ Analysis complete!")
            
        except Exception as e:
            print(f"❌ Analysis failed: {e}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='User Flow Analyzer - Analyze user event sequences')
    parser.add_argument('--user-id', '-u', help='Distinct ID to analyze')
    parser.add_argument('--days', '-d', type=int, default=30, help='Days to look back (default: 30)')
    parser.add_argument('--save', '-s', action='store_true', help='Save results to knowledge base')
    parser.add_argument('--save-events', '--se', action='store_true', help='Save events to individual file')
    parser.add_argument('--interactive', '-i', action='store_true', help='Run in interactive mode')
    parser.add_argument('--show-events', '-e', action='store_true', help='Show detailed events table')
    parser.add_argument('--show-knowledge', '-k', action='store_true', help='Show accumulated knowledge base')
    
    args = parser.parse_args()
    
    print_banner()
    
    # Initialize analyzer
    analyzer = UserFlowAnalyzer()
    
    # Show knowledge base if requested
    if args.show_knowledge:
        print("\n📚 ACCUMULATED FLOW KNOWLEDGE")
        print("="*60)
        knowledge = analyzer.load_flow_knowledge()
        print(knowledge)
        return
    
    # Interactive mode
    if args.interactive or not args.user_id:
        interactive_mode(analyzer)
        return
    
    # Single analysis mode
    print(f"\n🔍 Analyzing user {args.user_id} for the last {args.days} days...")
    
    try:
        # Fetch events
        events = analyzer.fetch_user_events(args.user_id, args.days)
        
        if not events:
            print(f"⚠️ No events found for user {args.user_id} in the last {args.days} days")
            return
        
        print(f"✅ Found {len(events)} events!")
        
        # Save events to individual file if requested
        if args.save_events:
            events_filename = analyzer.save_events_to_file(args.user_id, events, args.days)
        
        # Analyze sequence
        print("📊 Analyzing event sequence...")
        analysis = analyzer.analyze_event_sequence(events)
        
        if not analysis:
            print("❌ Could not analyze event sequence")
            return
        
        # Generate insights
        insights = analyzer.generate_flow_insights(analysis)
        
        # Display results
        print("\n" + "="*60)
        print("📋 FLOW ANALYSIS RESULTS")
        print("="*60)
        print(insights)
        
        # Show events table if requested
        if args.show_events:
            print_events_table(events)
        
        # Save analysis to knowledge base if requested
        if args.save:
            analyzer.save_flow_knowledge(args.user_id, analysis, insights)
        
        print("\n✅ Analysis complete!")
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")

if __name__ == "__main__":
    main()
