# Mixpanel User Activity Tracker with RAG Summaries

A Streamlit web app that

1. Pulls raw user-event data from the Mixpanel **Profile Event Activity API**.
2. Enriches each event with a human-readable description via a Pinecone-backed
   Retrieval-Augmented Generation (RAG) layer.
3. Generates a concise natural-language summary of what the user actually did
   during the selected time period.

---

## 1. Quick start

```bash
# clone / cd <repo>
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1️⃣  build the event-catalog index (once, or whenever the CSV changes)
python3 build_event_catalog.py

# 2️⃣  run the Streamlit app
streamlit run mixpanel_user_activity.py --server.headless true --server.port 8502
```
Open http://localhost:8502 in your browser.

---

## 2. Environment variables (`.env`)

```
# Mixpanel service-account creds
MIXPANEL_PROJECT_ID=your_project_id
MIXPANEL_USERNAME=service_account_username
MIXPANEL_SECRET=service_account_secret

# Pinecone
PINECONE_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
PINECONE_ENVIRONMENT=aws-us-east-1   # or gcp-starter, etc.

# OpenAI (for embeddings + summary LLM)
OPENAI_API_KEY=sk-...
```

> The code disables TLS verification (`network_utils.py`) for corporate proxy
> environments. Remove those patches in production.

---

## 3. Folder structure

```
.
├─ resources/
│   └─ event_catalog.csv      # event_name,description (edit as needed)
├─ build_event_catalog.py     # embeds CSV and upserts into Pinecone
├─ rag_utils.py               # enrichment + summary helpers
├─ mixpanel_user_activity.py  # Streamlit UI
├─ ingestion.py               # example of writing docs → Pinecone
├─ retrieval.py               # example of querying docs
└─ network_utils.py           # global SSL bypass helper
```

### event_catalog.csv
Edit / add rows:
```
event_name,description
app_open,User launched the mobile application
add_to_cart,User added an item to the shopping cart
checkout_started,User began the checkout process
purchase_completed,User completed a purchase transaction
```
Run `python3 build_event_catalog.py` afterwards to refresh the Pinecone index.

---

## 4. How it works

1. **build_event_catalog.py**
   • Reads the CSV
   • Uses `OpenAIEmbeddings` (`text-embedding-3-small`, 512 dims) to embed
     descriptions
   • Creates / upserts into the Pinecone serverless index `event-catalog`

2. **mixpanel_user_activity.py**
   • Sidebar asks for user IDs & date range
   • Fetches events via `/query/stream/query` endpoint
   • `rag_utils.enrich_with_event_desc(df)` → looks up each unique `event`
     name in Pinecone and adds `event_desc`
   • Displays enriched DataFrame
   • `rag_utils.summarize_session(df)` → sends trimmed JSON of events +
     catalog to GPT-3.5-turbo → prints a ≤200-word narrative under
     “📝 Session Summary (AI)”

---

## 5. Customising / extending

• **Adding events** – just edit the CSV and rerun the build script.
• **Change embedding model** – update `DIMENSIONS` + model name in
  `build_event_catalog.py` and `rag_utils.py`; delete & recreate the Pinecone
  index.
• **More context** – bump `k` in `rag_utils.enrich_with_event_desc` to fetch
  more nearest-neighbour descriptions.
• **Different summary style** – edit the prompt template in `rag_utils._PROMPT`.

---

## 6. Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| 404 `event-catalog not found` | Run `python3 build_event_catalog.py` first & restart Streamlit |
| SSL cert errors | The project monkey-patches SSL, but corporate proxies can still block. Check `network_utils.py` |
| `similarity_search_batch` AttributeError | Older langchain-pinecone: use the fallback loop (already handled) |

---

## 7. License
MIT – use freely, no warranties. 