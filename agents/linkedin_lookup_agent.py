import os
import httpx
import ssl
from dotenv import load_dotenv
from langchain.chains.summarize.map_reduce_prompt import prompt_template
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from langchain_core.tools import Tool

from langchain.agents import (create_react_agent,AgentExecutor)


from langchain import hub
from unicodedata import lookup

def lookup(name : str) ->str:
    llm = ChatOpenAI(temperature=0,model="gpt-4o-mini")
    template = """
    given the full name {name_of_person} i want you to get me a link of their
    Linkedin profile page.Your answer should only contain a url
    """

    prompt_template = PromptTemplate(template=template,
                                     input_variables=["name_of_person"])

    tools_for_agent = [Tool(name="Crawl Google 4 linkedin profile page",
                            func="?",
                            description="useful when you need get the linkedin url")]

    react_prompt = hub.pull("hwchase17/react")
    agent = create_react_agent(llm=llm,tools=tools_for_agent,prompt=react_prompt)
    agent_executor = AgentExecutor(agent=agent,tools=tools_for_agent,verbose=True)
    result = agent_executor.invoke({
        input({"input":prompt_template.format(name_of_the_person=name)})
    })
    linkdin_profile_url = result["output"]
    return linkdin_profile_url

if __name__ =="__main__":
    linkdin_url = lookup("Ankit Sharma")

