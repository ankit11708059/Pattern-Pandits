"""Entry point for data ingestion script."""

import os, sys, pathlib

# ---------------------------------------------------------------------------
# Ensure project root on sys.path
# ---------------------------------------------------------------------------
ROOT_DIR = pathlib.Path(__file__).resolve().parents[0]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# ---------------------------------------------------------------------------
# Disable SSL verification before ANY third-party network libs are imported
# ---------------------------------------------------------------------------
from network_utils import install_insecure_ssl  # noqa: E402

install_insecure_ssl()  # patches requests, httpx, urllib3, ssl

# Environment flags picked up by Pinecone SDK
os.environ.setdefault("PYTHONHTTPSVERIFY", "0")  # stdlib urllib / ssl
os.environ.setdefault("PINECONE_SSL_VERIFY", "0")  # pinecone-client env flag

# ---------------------------------------------------------------------------
# Now import the rest of the heavy networking libraries
# ---------------------------------------------------------------------------

from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import CharacterTextSplitter
from pydantic import BaseModel

from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore

# Patch Pinecone so any internal client constructed by LangChain defaults to
# ssl_verify=False to bypass corporate MITM certs.
import pinecone as _pc_module

_orig_pc_init = _pc_module.Pinecone.__init__

def _patched_pc_init(self, *args, **kwargs):
    kwargs.setdefault("ssl_verify", False)
    return _orig_pc_init(self, *args, **kwargs)

_pc_module.Pinecone.__init__ = _patched_pc_init  # type: ignore[method-assign]

load_dotenv()  # after path & SSL patches

import httpx


if __name__ == "__main__":
    print("Ingesting")
    loader = TextLoader("/Users/ankitsharma/PycharmProjects/langchain/medium.txt")
    document = loader.load()
    print("splitting")

    text_splitter = CharacterTextSplitter(chunk_size=1000,chunk_overlap=0)
    texts = text_splitter.split_documents(document)

    print(f"len is {len(texts)}")

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set in environment/.env file")

    embedding_model = OpenAIEmbeddings(
        api_key=OPENAI_API_KEY,
        model="text-embedding-3-small",  # outputs up to 1536 dims but allows down-projection
        dimensions=512,
        http_client=httpx.Client(verify=False, timeout=30.0),
    )

    # ------------------------------------------------------------------
    # Pinecone setup
    # ------------------------------------------------------------------
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east1-gcp")
    INDEX_NAME = os.getenv("INDEX_NAME")

    if not PINECONE_API_KEY or not INDEX_NAME:
        raise ValueError("PINECONE_API_KEY and INDEX_NAME must be set in environment/.env file")

    pc = Pinecone(api_key=PINECONE_API_KEY, ssl_verify=False)
    # Ensure index exists (create if missing)


    index = pc.Index(INDEX_NAME)

    print("Ingesting vectors → Pinecone ...")
    os.environ["PINECONE_ENVIRONMENT"] = PINECONE_ENVIRONMENT
    PineconeVectorStore.from_documents(texts, embedding_model, index_name=INDEX_NAME, pinecone_api_key=PINECONE_API_KEY)
    print("Finished ingestion ✅")