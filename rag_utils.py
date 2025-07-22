import os, json, httpx
import pandas as pd
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from langchain_core.prompts import PromptTemplate

DIMENSIONS = 512
INDEX_NAME = "event-catalog"

# Embedding + Pinecone clients (singleton)
_OPENAI_KEY = os.getenv("OPENAI_API_KEY")
_PINECONE_KEY = os.getenv("PINECONE_API_KEY")
_pc = Pinecone(api_key=_PINECONE_KEY, ssl_verify=False) if _PINECONE_KEY else None
_index = _pc.Index(INDEX_NAME) if _pc else None
_emb_model = (
    OpenAIEmbeddings(
        api_key=_OPENAI_KEY,
        model="text-embedding-3-small",
        dimensions=DIMENSIONS,
        http_client=httpx.Client(verify=False, timeout=30),
    )
    if _OPENAI_KEY
    else None
)
_catalog_vs = (
    PineconeVectorStore(index=_index, embedding=_emb_model) if _index and _emb_model else None
)


def enrich_with_event_desc(df: pd.DataFrame) -> pd.DataFrame:
    """Add event_desc column using the event catalog Pinecone index."""
    if _catalog_vs is None:
        df["event_desc"] = ""
        return df
    unique_events = df["event"].unique().tolist()

    # Some langchain-pinecone versions don't expose `similarity_search_batch`.
    if hasattr(_catalog_vs, "similarity_search_batch"):
        docs_per_query = _catalog_vs.similarity_search_batch(unique_events, k=1)
    else:
        # fallback: loop individually
        docs_per_query = [_catalog_vs.similarity_search(q, k=1) for q in unique_events]

    mapping = {
        evt: (docs_per_query[i][0].page_content if docs_per_query[i] else "")
        for i, evt in enumerate(unique_events)
    }
    df["event_desc"] = df["event"].map(mapping)
    return df


_PROMPT = PromptTemplate(
    input_variables=["events_json", "catalog_json"],
    template="""
You are a product analytics assistant.

User raw activity JSON:
{events_json}

Event catalog (name→description):
{catalog_json}

Write a concise chronological summary of the user's actions as BULLET POINTS only ("• text"). Group similar steps and highlight key milestones. Maximum 12 bullets.
""",
)


def summarize_session(df: pd.DataFrame) -> str:
    if _OPENAI_KEY is None:
        return "(OpenAI key missing — cannot generate summary)"
    events = df[["time", "event", "event_desc", "properties"]].to_dict("records")
    catalog = {
        row["event"]: row["event_desc"] for _, row in df.drop_duplicates("event").iterrows()
    }
    llm = ChatOpenAI(
        api_key=_OPENAI_KEY,
        temperature=0,
        model="gpt-3.5-turbo",
        http_client=httpx.Client(verify=False, timeout=30),
    )
    chain = _PROMPT | llm
    return chain.invoke(
        {
            "events_json": json.dumps(events, default=str)[:8000],
            "catalog_json": json.dumps(catalog)[:2000],
        }
    ) 