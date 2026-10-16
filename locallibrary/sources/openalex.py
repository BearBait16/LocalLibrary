"""Open-access research papers from OpenAlex (https://help.openalex.org)."""
import sys

import httpx

from locallibrary import db, embed
from locallibrary.config import config
from locallibrary.ingest import USER_AGENT, summary_text
from locallibrary.models import RESEARCH_PAPER, Source

WORKS_URL = "https://api.openalex.org/works"
MAX_QUERY_CHARS = 2000  # semantic search ignores anything longer


def rebuild_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """OpenAlex stores abstracts as {word: [positions]}; put the words back in order."""
    if not inverted_index:
        return ""
    positions = {pos: word for word, places in inverted_index.items() for pos in places}
    return " ".join(positions[i] for i in sorted(positions))


def fetch_works(query: str) -> list[dict]:
    # Semantic search matches by meaning; `has_pdf_url` isn't supported with it, so PDFs are
    # filtered below. Only one search parameter is allowed per request.
    params = {
        "search.semantic": query[:MAX_QUERY_CHARS],
        "filter": "is_oa:true,has_abstract:true,type:article|review,language:en",
        "per_page": 50,
        "select": "id,display_name,best_oa_location,abstract_inverted_index",
    }
    if config.openalex_api_key:
        params["api_key"] = config.openalex_api_key
    if config.openalex_email:
        params["mailto"] = config.openalex_email
    resp = httpx.get(WORKS_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.json()["results"]


def search(query: str, limit: int = 15) -> list[Source]:
    """Find open-access papers with a PDF, upsert them with summary embeddings, return them."""
    papers = []
    for work in fetch_works(query):
        pdf_url = (work.get("best_oa_location") or {}).get("pdf_url")
        if not pdf_url or not work.get("display_name"):
            continue
        papers.append(Source(title=work["display_name"], source_type=RESEARCH_PAPER, origin="openalex",
                             url=pdf_url, description=rebuild_abstract(work.get("abstract_inverted_index"))))
        if len(papers) == limit:
            break
    vectors = embed.embed_documents([summary_text(p) for p in papers])
    return [db.upsert_source(p, v) for p, v in zip(papers, vectors)]


if __name__ == "__main__":
    db.init_schema()
    for paper in search(" ".join(sys.argv[1:]) or "intro to statistics"):
        print(f"#{paper.id} {paper.title[:90]}\n    {paper.url}")
