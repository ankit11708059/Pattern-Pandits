# Mixpanel User Activity Tracker

A Streamlit web application for querying user activity data from Mixpanel using the Profile Event Activity API.

## Features

- 🔍 Query user activity by distinct user IDs
- 📅 Flexible date range selection
- 📊 Visual analytics with charts and metrics
- 📋 Detailed activity data table with filtering
- 📥 CSV export functionality
- 🔧 Easy configuration via environment variables
- 🔒 SSL certificate handling for corporate networks

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Mixpanel Credentials

Add the following to your `.env` file:

```env
# Mixpanel API Configuration
MIXPANEL_PROJECT_ID=your_mixpanel_project_id
MIXPANEL_USERNAME=your_service_account_username
MIXPANEL_SECRET=your_service_account_secret
```

### 3. Get Mixpanel Credentials

1. **Project ID**: 
   - Go to your Mixpanel project settings
   - Look for "Project ID" (usually a string like "abc123def456")
   - **Note**: This should be the actual project ID, not the project token

2. **Service Account Credentials**:
   - Go to Organization Settings > Service Accounts
   - Create a new service account or use existing one
   - Copy the username and secret

### 4. Run the Application

```bash
# Activate virtual environment
source .venv/bin/activate

# Run Streamlit app
streamlit run mixpanel_user_activity.py
```

## Troubleshooting

### 400 Bad Request Error

If you get a "400 Client Error: Bad Request" or "Invalid project ID" error:

1. **Check Project ID Format**:
   - Make sure you're using the Project ID, not the Project Token
   - Project ID is usually found in Project Settings
   - It should be a string like "abc123def456789"

2. **Verify Credentials**:
   - Ensure your service account has the correct permissions
   - Check that username and secret are correct
   - Make sure the service account has access to the specific project

3. **Check API Endpoint**:
   - The application now uses the correct Mixpanel API endpoint
   - SSL verification is disabled for corporate networks

### SSL Certificate Issues

If you encounter SSL certificate errors:
- The application automatically handles SSL certificate issues
- SSL verification is disabled by default
- SSL warnings are suppressed

### Missing Data

If no activity data is found:
- Check that the user IDs (distinct_ids) are correct
- Verify the date range has data
- Ensure the users performed events in the specified time period

## Usage

1. **Configure Credentials**: Set up your `.env` file with valid Mixpanel credentials
2. **Enter User IDs**: Input one or more user IDs (distinct_ids) in the sidebar
3. **Select Date Range**: Choose the date range for activity data
4. **Query Data**: Click "Get User Activity" to fetch and display the data
5. **Analyze Results**: View metrics, charts, and detailed activity table
6. **Export Data**: Download the results as CSV for further analysis

## API Endpoints Used

- **Profile Event Activity**: `/api/query/stream/query`
- **Authentication**: Basic Auth with service account credentials

## Requirements

- Python 3.10+
- Streamlit
- Requests
- Pandas
- Valid Mixpanel service account with API access

## File Structure

```
├── mixpanel_user_activity.py  # Main application
├── requirements.txt           # Dependencies
├── README_MIXPANEL.md        # This file
└── .env                      # Environment variables (create this)
```

## Security Notes

- The `.env` file is ignored by git for security
- SSL verification is disabled for corporate network compatibility
- Service account credentials are required for API access

## Support

For issues with:
- **Mixpanel API**: Check [Mixpanel API Documentation](https://developer.mixpanel.com/reference/overview)
- **Service Accounts**: Visit [Service Account Setup](https://developer.mixpanel.com/reference/service-accounts)
- **Profile Activity API**: See [Profile Event Activity API](https://developer.mixpanel.com/reference/profile-event-activity) 