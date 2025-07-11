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

# Ensure project root is in sys.path so that `import tools` works when running
# this file directly from the agents/ directory.
import sys, pathlib
ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import ssl
try:
    from dotenv import load_dotenv
except ImportError:  # Fallback if python-dotenv is not installed
    def load_dotenv(*args, **kwargs):
        return None
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import httpx

from langchain_core.tools import Tool

from langchain.agents import create_react_agent, AgentExecutor

from langchain import hub

from tools.tools import get_profile_url_tavily

# ---------------------------------------------------------------------------
# Disable SSL verification globally (work-around for self-signed certificates)
# ---------------------------------------------------------------------------
from network_utils import install_insecure_ssl

install_insecure_ssl()

# Load environment variables
load_dotenv()

# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

def linkedin_lookup(name: str) -> str:
    """Return the LinkedIn profile URL for a given full name using an LLM-powered
    agent that searches Google via the TavilySearchResults tool.
    """
    # Create the LLM (uses the global SSL bypass so no cert issues)
    http_client = httpx.Client(verify=False, timeout=30.0)
    llm = ChatOpenAI(
        temperature=0,
        model="gpt-3.5-turbo",
        openai_api_key=os.environ["OPENAI_API_KEY"],
        http_client=http_client,
    )

    template = (
        "given the designation {name_of_person} i want you to get me a link of their\n"
        "Linkedin profile page. Your answer should only contain a url"
    )
    prompt_template = PromptTemplate(
        template=template,
        input_variables=["name_of_person"],
    )

    tools_for_agent = [
        Tool(
            name="Crawl Google 4 linkedin profile page",
            func=get_profile_url_tavily,
            description="useful when you need get the linkedin url",
        )
    ]

    # Pull the standard ReAct prompt from LangChain Hub
    react_prompt = hub.pull("hwchase17/react")

    # Create the agent and executor
    agent = create_react_agent(llm=llm, tools=tools_for_agent, prompt=react_prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools_for_agent, verbose=True)

    # Invoke the agent with the prepared prompt
    result = agent_executor.invoke(
        {
            "input": prompt_template.format(name_of_person=name)
        }
    )

    linkedin_profile_url = result["output"]
    return linkedin_profile_url


if __name__ == "__main__":
    url = linkedin_lookup("Android developer at cash app")
    print(f"LinkedIn URL: {url}")

