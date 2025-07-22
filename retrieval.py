"""Retrieve answers from Pinecone-indexed documents."""
# ---------------------------------------------------------------------------
# Standard libs & SSL monkey-patching (reuse network_utils)
# ---------------------------------------------------------------------------
import os, sys, pathlib, httpx

ROOT_DIR = pathlib.Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from network_utils import install_insecure_ssl  # noqa: E402

install_insecure_ssl()

# ---------------------------------------------------------------------------
# Third-party imports (after SSL patch)
# ---------------------------------------------------------------------------

from dotenv import load_dotenv
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import PromptTemplate
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain import hub

from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore

# Ensure Pinecone clients always run with ssl_verify=False
import pinecone as _pc_module

_orig_pc_init = _pc_module.Pinecone.__init__

def _patched_pc_init(self, *args, **kwargs):
    kwargs.setdefault("ssl_verify", False)
    return _orig_pc_init(self, *args, **kwargs)

_pc_module.Pinecone.__init__ = _patched_pc_init  # type: ignore[method-assign]

load_dotenv()

# ---------------------------------------------------------------------------
# Config & Clients
# ---------------------------------------------------------------------------

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY missing in environment")
if not PINECONE_API_KEY or not INDEX_NAME:
    raise ValueError("PINECONE_API_KEY / INDEX_NAME missing in environment")

    embedding_model = OpenAIEmbeddings(
    api_key=OPENAI_API_KEY,
    model="text-embedding-3-small",
        dimensions=512,
        http_client=httpx.Client(verify=False, timeout=30.0),
    )

    llm = ChatOpenAI(temperature=0, http_client=httpx.Client(verify=False))

pc = Pinecone(api_key=PINECONE_API_KEY)  # ssl_verify patched to False globally
index = pc.Index(INDEX_NAME)

# Vector store connected to existing index
vector_store = PineconeVectorStore(index=index, embedding=embedding_model)

# ---------------------------------------------------------------------------
# Retrieval chain
# ---------------------------------------------------------------------------

retrieval_prompt = hub.pull("langchain-ai/retrieval-qa-chat")
combine_docs_chain = create_stuff_documents_chain(llm, retrieval_prompt)
# Retrieve more documents for richer context
retriever = vector_store.as_retriever(search_kwargs={"k": 10})
retrieval_chain = create_retrieval_chain(retriever, combine_docs_chain)


if __name__ == "__main__":
    print("Retrieving ...")

    query = (
        "which senior engineer contributed in , How We Slashed Our Build Times at slice article ?"
    )

    result = retrieval_chain.invoke({"input": query})

    print("\nAnswer:\n", result)