from typing import List,Dict,Any

from langchain_core.output_parsers import PydanticOutputParser

from pydantic import BaseModel,Field


class Summary(BaseModel):
    summary: str = Field(description="interesting facts about me")
    facts: List[str] = Field(description="interesting facts about them")