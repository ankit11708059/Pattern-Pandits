# Mixpanel User Activity Tracker with Cursor Integration

## 🚀 New Features

Your Mixpanel app now has **Cursor-like AI capabilities** integrated directly into the chat interface!

## 🤖 What's New

### Dual-Purpose AI Assistant
The chat interface now handles both:
- **📊 Mixpanel Data Analysis** - User activity, events, trends
- **🤖 Cursor-like Development Help** - Code analysis, file operations, debugging

### Cursor-like Capabilities

#### 📁 File Operations
- `list files` - See all project files
- `read filename.py` - Read any file in your project
- `search pattern` - Search for code patterns across files

#### 🔧 Code Analysis
- Ask about functions, classes, imports
- Get help with debugging
- Code explanations and suggestions
- Error analysis and fixes

#### 💬 Natural Language
- "Explain this function"
- "Help me debug this error"
- "How does MixpanelUserActivity work?"
- "What files are in this project?"
- "Search for authentication code"

## 🛠️ Setup

### Required Environment Variables

Create a `.env` file with:

```bash
# Mixpanel Configuration
MIXPANEL_PROJECT_ID=your_mixpanel_project_id
MIXPANEL_USERNAME=your_service_account_username
MIXPANEL_SECRET=your_service_account_secret

# OpenAI Configuration (for enhanced AI responses)
OPENAI_API_KEY=your_openai_api_key
```

### Optional: OpenAI Integration
- Add your OpenAI API key for enhanced AI responses
- Without it, you still get basic Cursor-like functionality
- With it, you get intelligent code analysis and suggestions

## 🎯 Usage Examples

### Mixpanel Queries
- "Show me activity for user abc123"
- "What are the top events today?"
- "Get user summary for xyz789"

### Development Queries
- "List all Python files"
- "Read mixpanel_user_activity.py"
- "Search for MixpanelUserActivity"
- "Explain the CursorAssistant class"
- "Help me debug API connection issues"

### Mixed Queries
- "How does the user activity API work?"
- "Show me the code that handles Mixpanel authentication"
- "What files handle user data processing?"

## 🚀 Quick Actions

The interface includes quick action buttons for:

**📊 Mixpanel Actions:**
- Get User Summary
- Top Events Today
- Activity Trends

**🤖 Cursor Actions:**
- List Files
- Search Code
- Read File

## 🔧 Technical Details

### CursorAssistant Class
- File reading and navigation
- Code search using grep
- Project structure analysis
- OpenAI integration for intelligent responses

### Enhanced Chat Processing
- Keyword detection for query routing
- Context-aware responses
- File and code pattern extraction
- Integrated help system

## 🌟 Benefits

1. **Unified Interface** - Both data analysis and development help in one place
2. **Context Awareness** - AI understands your project structure
3. **Code Navigation** - Easy file reading and searching
4. **Development Support** - Debugging and code analysis help
5. **Natural Language** - Ask questions in plain English

## 🚀 Running the App

```bash
source .venv/bin/activate
streamlit run mixpanel_user_activity.py --server.port 8504
```

Visit: http://localhost:8504

Navigate to the **"AI Chat Assistant"** tab to experience the new Cursor-like capabilities! 