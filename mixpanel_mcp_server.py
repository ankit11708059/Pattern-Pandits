#!/usr/bin/env python3
"""
MCP Server for Mixpanel User Activity
Allows Cursor to interact with Mixpanel user activity data through MCP protocol
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
from pydantic import AnyUrl
from dotenv import load_dotenv

# Import our existing Mixpanel functionality
from mixpanel_user_activity import MixpanelUserActivity

# Load environment variables
load_dotenv()

# Initialize MCP server
server = Server("mixpanel-user-activity")

# Initialize Mixpanel client
MIXPANEL_PROJECT_ID = os.getenv("MIXPANEL_PROJECT_ID")
MIXPANEL_USERNAME = os.getenv("MIXPANEL_USERNAME")
MIXPANEL_SECRET = os.getenv("MIXPANEL_SECRET")

if not all([MIXPANEL_PROJECT_ID, MIXPANEL_USERNAME, MIXPANEL_SECRET]):
    raise ValueError("Missing Mixpanel credentials in environment variables")

mixpanel_client = MixpanelUserActivity(MIXPANEL_PROJECT_ID, MIXPANEL_USERNAME, MIXPANEL_SECRET)

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available Mixpanel tools"""
    return [
        Tool(
            name="get_user_activity",
            description="Get user activity data from Mixpanel for specific user IDs",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of user IDs (distinct_ids) to get activity for"
                    },
                    "from_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (optional, defaults to 7 days ago)"
                    },
                    "to_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format (optional, defaults to today)"
                    }
                },
                "required": ["user_ids"]
            }
        ),
        Tool(
            name="analyze_user_behavior",
            description="Analyze user behavior patterns from Mixpanel activity data",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of user IDs to analyze"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to analyze (default: 7)"
                    }
                },
                "required": ["user_ids"]
            }
        ),
        Tool(
            name="get_user_summary",
            description="Get a summary of user activity including key metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Single user ID to get summary for"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to summarize (default: 30)"
                    }
                },
                "required": ["user_id"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls"""
    
    if name == "get_user_activity":
        user_ids = arguments.get("user_ids", [])
        from_date = arguments.get("from_date")
        to_date = arguments.get("to_date")
        
        # Set default dates if not provided
        if not from_date:
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
        
        # Get activity data
        response = mixpanel_client.get_user_activity(user_ids, from_date, to_date)
        
        if "error" in response:
            return [TextContent(type="text", text=f"Error: {response['error']}")]
        
        # Format the response
        df = mixpanel_client.format_activity_data(response)
        
        if df.empty:
            return [TextContent(type="text", text="No activity data found for the specified users and date range.")]
        
        # Create summary
        summary = f"""
# Mixpanel User Activity Summary

**Date Range:** {from_date} to {to_date}
**Users:** {', '.join(user_ids)}

## Key Metrics:
- **Total Events:** {len(df)}
- **Unique Users:** {df['user_id'].nunique()}
- **Unique Event Types:** {df['event'].nunique()}
- **Date Range:** {df['time'].min()} to {df['time'].max()}

## Top Events:
{df['event'].value_counts().head(10).to_string()}

## Recent Activity:
{df[['time', 'user_id', 'event', 'platform', 'city']].head(20).to_string()}
"""
        
        return [TextContent(type="text", text=summary)]
    
    elif name == "analyze_user_behavior":
        user_ids = arguments.get("user_ids", [])
        days = arguments.get("days", 7)
        
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        
        # Get activity data
        response = mixpanel_client.get_user_activity(user_ids, from_date, to_date)
        
        if "error" in response:
            return [TextContent(type="text", text=f"Error: {response['error']}")]
        
        df = mixpanel_client.format_activity_data(response)
        
        if df.empty:
            return [TextContent(type="text", text="No activity data found for analysis.")]
        
        # Analyze behavior patterns
        analysis = f"""
# User Behavior Analysis

**Analysis Period:** Last {days} days
**Users Analyzed:** {', '.join(user_ids)}

## Activity Patterns:
- **Most Active User:** {df['user_id'].value_counts().index[0]} ({df['user_id'].value_counts().iloc[0]} events)
- **Most Common Event:** {df['event'].value_counts().index[0]} ({df['event'].value_counts().iloc[0]} occurrences)
- **Peak Activity Day:** {df['time'].dt.date.value_counts().index[0]}

## Platform Usage:
{df['platform'].value_counts().to_string()}

## Geographic Distribution:
{df['city'].value_counts().head(10).to_string()}

## Event Frequency by User:
{df.groupby('user_id')['event'].count().to_string()}

## Hourly Activity Pattern:
{df['time'].dt.hour.value_counts().sort_index().to_string()}
"""
        
        return [TextContent(type="text", text=analysis)]
    
    elif name == "get_user_summary":
        user_id = arguments.get("user_id")
        days = arguments.get("days", 30)
        
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        
        # Get activity data for single user
        response = mixpanel_client.get_user_activity([user_id], from_date, to_date)
        
        if "error" in response:
            return [TextContent(type="text", text=f"Error: {response['error']}")]
        
        df = mixpanel_client.format_activity_data(response)
        
        if df.empty:
            return [TextContent(type="text", text=f"No activity data found for user {user_id}.")]
        
        # Create detailed user summary
        user_df = df[df['user_id'] == user_id]
        
        summary = f"""
# User Summary: {user_id}

**Analysis Period:** Last {days} days ({from_date} to {to_date})

## Activity Overview:
- **Total Events:** {len(user_df)}
- **Unique Event Types:** {user_df['event'].nunique()}
- **First Activity:** {user_df['time'].min()}
- **Last Activity:** {user_df['time'].max()}
- **Most Active Day:** {user_df['time'].dt.date.value_counts().index[0] if not user_df.empty else 'N/A'}

## Top Events:
{user_df['event'].value_counts().head(10).to_string()}

## Platform/Browser Usage:
- **Primary Platform:** {user_df['platform'].mode().iloc[0] if not user_df['platform'].mode().empty else 'Unknown'}
- **Primary Browser:** {user_df['browser'].mode().iloc[0] if not user_df['browser'].mode().empty else 'Unknown'}

## Location:
- **City:** {user_df['city'].mode().iloc[0] if not user_df['city'].mode().empty else 'Unknown'}
- **Country:** {user_df['country'].mode().iloc[0] if not user_df['country'].mode().empty else 'Unknown'}

## Recent Activity (Last 10 Events):
{user_df[['time', 'event', 'platform', 'city']].head(10).to_string()}
"""
        
        return [TextContent(type="text", text=summary)]
    
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="mixpanel-user-activity",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities=None,
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main()) 