import os
import httpx
import ssl
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

# Load environment variables from .env file
load_dotenv()

# SSL Fix: Create custom HTTP client with SSL verification disabled
def create_custom_client():
    return httpx.Client(
        verify=False,
        timeout=30.0,
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=50)
    )

information = """
i want to start using mk677 , but i want to track my prolactin levels and insulinn levels
what tests should i be doing to track these before so that i can compare it will future levels
"""

def main():
    summary_template = """
    given the information {information}
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
        res = chain.invoke(input={"information": information})
        print("✅ Success! Response:")
        print(res)
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        print("\n🔧 Trying alternative approach...")
        
        # Fallback: Use environment variable to disable SSL globally
        os.environ['PYTHONHTTPSVERIFY'] = '0'
        ssl._create_default_https_context = ssl._create_unverified_context
        
        try:
            llm_fallback = ChatOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"), 
                temperature=0, 
                model="gpt-3.5-turbo"
            )
            chain_fallback = summary_prompt_template | llm_fallback
            res = chain_fallback.invoke(input={"information": information})
            print("✅ Success with fallback! Response:")
            print(res)
        except Exception as e2:
            print(f"❌ Fallback also failed: {e2}")

if __name__ == "__main__":
    main()
