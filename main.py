import os
# ---------------------------------------------------------------------------
# Disable LangSmith/LangChain tracing if no API key is supplied
# ---------------------------------------------------------------------------
for _var in (
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_TRACING",
    "LANGSMITH_TRACING",
    "LANGCHAIN_ENDPOINT",
    "LANGSMITH_ENDPOINT",
):
    os.environ.pop(_var, None)

import warnings
warnings.filterwarnings(
    "ignore",
    message=".*LangSmithMissingAPIKeyWarning.*",
)
import httpx
import ssl
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from linkdin import scrape_linkedin_profile

# Load environment variables from .env file
load_dotenv()

# SSL Fix: Create custom HTTP client with SSL verification disabled
def create_custom_client():
    return httpx.Client(
        verify=False,
        timeout=30.0,
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=50)
    )

def main():
    summary_template = """
    given the linkedin information {information} about the person , I want to create
    1. A short summary
    2. two interesting facts about them
    """

    summary_prompt_template = PromptTemplate(input_variables=["information"], template=summary_template)
    
    # Create custom HTTP client
    custom_client = create_custom_client()
    
    # Create LLM with custom HTTP client
    llm = ChatOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"), 
        temperature=0, 
        model="gpt-3.5-turbo",
        http_client=custom_client
    )
    
    chain = summary_prompt_template | llm
    
    try:
        print("🔄 Making API call to OpenAI with SSL fix...")
        linkdindata = scrape_linkedin_profile()
        res = chain.invoke(input={"information": linkdindata})
        print("✅ Success! Response:")
        print(res)
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        print("\n🔧 Trying alternative approach...")
        
        # Fallback: Use environment variable to disable SSL globally
        os.environ['PYTHONHTTPSVERIFY'] = '0'
        ssl._create_default_https_context = ssl._create_unverified_context


if __name__ == "__main__":
    main()
