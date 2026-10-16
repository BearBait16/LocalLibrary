"""Research-page logic: answer questions from a shelf book's sources, and find similar sources."""
import re
import sys
from dataclasses import dataclass, field

from locallibrary import db, embed, llm
from locallibrary.models import Source

SNIPPET_CHARS = 160


@dataclass
class Citation:
    source_id: int
    source_title: str
    page: int
    snippet: str


@dataclass
class Answer:
    text: str
    citations: list[Citation] = field(default_factory=list)


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= SNIPPET_CHARS else text[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"


def cited_numbers(text: str, count: int) -> list[int]:
    """Passage numbers cited like [2] or [1, 3], in first-cited order, within 1..count."""
    numbers = []
    for group in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", text):
        for n in map(int, group.split(",")):
            if 1 <= n <= count and n not in numbers:
                numbers.append(n)
    return numbers


def ask(question: str, source_ids: list[int], limit: int = 6) -> Answer:
    chunks = db.search_chunks(embed.embed_query(question), source_ids, limit)
    if not chunks:
        return Answer("None of this book's sources have readable passages yet.")
    titles = {s.id: s.title for s in db.get_sources(list({c.source_id for c in chunks}))}
    text = llm.answer(question, chunks, titles)
    numbers = cited_numbers(text, len(chunks)) or list(range(1, len(chunks) + 1))
    citations, seen = [], set()
    for n in numbers:
        c = chunks[n - 1]
        if (c.source_id, c.page) not in seen:  # several passages can come from one page
            seen.add((c.source_id, c.page))
            citations.append(Citation(c.source_id, titles.get(c.source_id, ""), c.page, _snippet(c.text)))
    return Answer(text, citations)


def similar_sources(source_id: int, limit: int = 8, exclude_ids: list[int] | None = None) -> list[Source]:
    """Nearest sources by summary embedding, excluding this one (and any in `exclude_ids`)."""
    vector = db.get_summary_embedding(source_id)
    if vector is None:
        return []
    return [s for s, _ in db.search_sources(vector, limit=limit, exclude_ids=[source_id, *(exclude_ids or [])])]


if __name__ == "__main__":
    ids = [int(i) for i in sys.argv[1].split(",")]
    result = ask(" ".join(sys.argv[2:]), ids)
    print(result.text, "\n")
    for c in result.citations:
        print(f"- {c.source_title}, p. {c.page}: {c.snippet}")
