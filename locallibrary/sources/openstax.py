"""OpenStax textbook catalog: stored as un-downloaded textbook sources."""
import html
import json
import re
from pathlib import Path

import httpx

from locallibrary import db, embed
from locallibrary.ingest import USER_AGENT, summary_text
from locallibrary.models import TEXTBOOK, Source

CATALOG_URL = "https://openstax.org/apps/cms/api/v2/pages/"
SEED_FILE = Path(__file__).with_name("openstax_seed.json")


def strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def fetch_catalog() -> list[dict]:
    """Return [{title, description, url}] for live OpenStax books that have a PDF."""
    params = {
        "type": "books.Book",
        "fields": "title,description,high_resolution_pdf_url,book_state",
        "limit": 250,
    }
    resp = httpx.get(CATALOG_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return [
        {"title": b["title"], "description": strip_html(b.get("description", "")), "url": b["high_resolution_pdf_url"]}
        for b in resp.json()["items"]
        if b.get("book_state") == "live" and b.get("high_resolution_pdf_url")
    ]


def sync_catalog(progress_callback=None) -> int:
    """Upsert the catalog with summary embeddings. Returns the number of books."""
    try:
        books = fetch_catalog()
    except (httpx.HTTPError, KeyError, ValueError):
        books = json.loads(SEED_FILE.read_text())
    sources = [Source(title=b["title"], source_type=TEXTBOOK, origin="openstax", url=b["url"],
                      description=b["description"]) for b in books]
    vectors = embed.embed_documents([summary_text(s) for s in sources], progress_callback)
    for source, vector in zip(sources, vectors):
        db.upsert_source(source, vector)
    return len(sources)


if __name__ == "__main__":
    db.init_schema()
    print(f"Synced {sync_catalog()} OpenStax books ({db.count_sources(TEXTBOOK)} textbooks in library)")
