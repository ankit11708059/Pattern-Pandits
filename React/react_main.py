from typing import Union, List

from dotenv import load_dotenv
from langchain.agents.output_parsers import ReActSingleInputOutputParser
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool, render_text_description, Tool
from langchain_openai import ChatOpenAI

# Standard libs
import sys, pathlib

# Ensure project root is on sys.path before importing internal modules
ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# Third-party libs
import httpx

# Internal utilities (now importable)
from network_utils import install_insecure_ssl

# Disable TLS verification and suppress warnings globally
install_insecure_ssl()

load_dotenv()

@tool
def get_text_length(text:str) ->int:
    """ return the length of text by character"""
    text = text.strip("'\n").strip('"')
    return len(text)


def find_tool_by_name(tools : List[Tool] ,tool_name : str) -> Tool:
     for tool in tools:
        if tool.name== tool_name:
            return tool



if __name__=="__main__":
    tools = [get_text_length]

    template = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}
    """


    prompt_template = ((PromptTemplate.from_template(template=template)).
                       partial(tools=render_text_description(tools),
                               tool_names = ", ".join([t.name for t in tools])))

    llm = ChatOpenAI(temperature=0, http_client=httpx.Client(verify=False)).bind(stop=["Observation:"])
    intermediate_steps = []

    # Ensure the prompt is rendered BEFORE sending to the LLM.
    agent = (
        prompt_template
        | llm | ReActSingleInputOutputParser() # sends rendered prompt to the chat model
    )

    agent_step : Union[AgentAction,AgentFinish] = agent.invoke({
        "input": "What is length of 'DOG' in characters?",
        "agent_scratchpad": ""
    })

    print(agent_step)

    if isinstance(agent_step,AgentAction):
        tool_name = agent_step.tool
        tool_to_use = find_tool_by_name(tools, tool_name)
        tool_input = agent_step.tool_input

        observation = tool_to_use.func(str(tool_input))
        print(observation)
        intermediate_steps.append((agent_step,str(observation)))

