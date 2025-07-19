import os, csv, httpx
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()
OPENAI_KEY   = os.getenv("OPENAI_API_KEY")
PINECONE_KEY = os.getenv("PINECONE_API_KEY")
# PINECONE_ENVIRONMENT should look like "aws-us-east-1" or "gcp-starter"
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT", "aws-us-east-1")
INDEX_NAME   = "event-catalog"
DIMENSIONS   = 512
CSV_PATH     = "resources/event_catalog.csv"

assert OPENAI_KEY, "OPENAI_API_KEY missing"
assert PINECONE_KEY, "PINECONE_API_KEY missing"

# ---------------------------------------------------------------------------
# Load catalog from CSV
# ---------------------------------------------------------------------------
records = []
with open(CSV_PATH, newline="") as f:
    for row in csv.DictReader(f):
        if not row["event_name"].strip():
            continue
        records.append(row)

# ---------------------------------------------------------------------------
# Embed descriptions
# ---------------------------------------------------------------------------
emb_model = OpenAIEmbeddings(
    api_key=OPENAI_KEY,
    model="text-embedding-3-small",
    dimensions=DIMENSIONS,
    http_client=httpx.Client(verify=False, timeout=30),
)

vectors = [
    (rec["event_name"], emb_model.embed_query(rec["description"]), rec) for rec in records
]

# ---------------------------------------------------------------------------
# Upsert into Pinecone
# ---------------------------------------------------------------------------
pc = Pinecone(api_key=PINECONE_KEY, ssl_verify=False)
# Split env into cloud and region parts
if INDEX_NAME not in [i.name for i in pc.list_indexes()]:
    print("Creating Pinecone index …")
    if "-" in PINECONE_ENV:
        parts = PINECONE_ENV.split("-", 1)
        cloud = parts[0]
        region = parts[1]
    else:
        cloud = "aws"
        region = PINECONE_ENV

    pc.create_index(
        name=INDEX_NAME,
        dimension=DIMENSIONS,
        metric="cosine",
        spec=ServerlessSpec(cloud=cloud, region=region),
    )
index = pc.Index(INDEX_NAME)
index.upsert(vectors)
print(f"✅  Upserted {len(vectors)} event vectors to {INDEX_NAME}") 