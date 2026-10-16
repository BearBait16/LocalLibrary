"""Optional web source finding with Gemini + Google Search grounding.

Gemini is only used here, when the user ticks "Also search the web". It never answers RAG questions.
"""
import json
import re
import sys

from locallibrary import db, embed
from locallibrary.config import config
from locallibrary.ingest import summary_text
from locallibrary.models import RESEARCH_PAPER, TEXTBOOK, WEB_ARTICLE, Source

PROMPT = """Use Google Search to find the {limit} best freely readable web sources for someone
researching this topic: "{query}".
Prefer in-depth articles, tutorials, lecture notes and open-access papers. Each URL must be a page
or PDF that can be read without logging in or paying.

Reply with only a JSON array, no other text. Each item:
{{"title": "...", "url": "https://...", "type": "web_article" | "research_paper" | "textbook",
  "reason": "one short line on why it helps"}}"""

TYPES = {WEB_ARTICLE, RESEARCH_PAPER, TEXTBOOK}


def parse_results(text: str) -> list[dict]:
    """Pull the first JSON array out of the model's reply and keep well-formed items."""
    text = re.sub(r"```(?:json)?", "", text or "")
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        items = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    results = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        url, title = str(item.get("url", "")).strip(), str(item.get("title", "")).strip()
        if not url.startswith(("http://", "https://")) or not title:
            continue
        kind = item.get("type") if item.get("type") in TYPES else WEB_ARTICLE
        results.append({"title": title, "url": url, "type": kind, "reason": str(item.get("reason", "")).strip()})
    return results


def find_web_sources(query: str, limit: int = 8) -> list[tuple[Source, str]]:
    """Return (source, reason) pairs found by Gemini, upserted as origin 'gemini'. [] without a key."""
    if not config.gemini_enabled:
        return []
    from google import genai

    client = genai.Client(api_key=config.gemini_api_key)
    interaction = client.interactions.create(
        model=config.gemini_model,
        input=PROMPT.format(query=query, limit=limit),
        tools=[{"type": "google_search"}],
        store=False,
    )
    items = parse_results(interaction.output_text)[:limit]
    sources = [Source(title=i["title"], source_type=i["type"], origin="gemini", url=i["url"],
                      description=i["reason"]) for i in items]
    vectors = embed.embed_documents([summary_text(s) for s in sources])
    return [(db.upsert_source(s, v), i["reason"]) for s, v, i in zip(sources, vectors, items)]


if __name__ == "__main__":
    if not config.gemini_enabled:
        print("GEMINI_API_KEY is not set; web search is disabled.")
        sys.exit(0)
    db.init_schema()
    for source, reason in find_web_sources(" ".join(sys.argv[1:]) or "intro to statistics"):
        print(f"#{source.id} [{source.source_type}] {source.title}\n    {source.url}\n    {reason}")
