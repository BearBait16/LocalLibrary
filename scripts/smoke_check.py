"""Phase 0 check: Postgres reachable, pgvector enabled, Ollama returns a 768-d embedding."""
import os

import ollama
import psycopg
from dotenv import load_dotenv

load_dotenv()

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    version = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()[0]
    print(f"Postgres OK, pgvector {version}")

client = ollama.Client(host=os.environ["OLLAMA_HOST"])
result = client.embed(model=os.environ["EMBED_MODEL"], input="search_query: hello world")
print(f"Ollama OK, embedding length {len(result.embeddings[0])}")
