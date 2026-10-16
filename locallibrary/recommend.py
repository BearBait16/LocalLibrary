"""Search-page logic: pick a starting textbook and related papers for a query."""
import logging
import sys
from dataclasses import dataclass, field

from locallibrary import db, embed, llm
from locallibrary.models import RESEARCH_PAPER, TEXTBOOK, Source
from locallibrary.sources import openalex

log = logging.getLogger(__name__)

TEXTBOOK_CANDIDATES = 5
PAPER_CANDIDATES = 15
MIN_PAPERS, MAX_PAPERS = 3, 6


@dataclass
class Recommendation:
    textbook: Source | None
    papers: list[Source]
    reasons: dict[int, str] = field(default_factory=dict)  # source id -> one-line reason
    used_fallback: bool = False


def _candidates(query_vec: list[float], source_type: str, limit: int) -> list[Source]:
    """Nearest sources by summary, plus downloaded sources whose passages match well."""
    found = [s for s, _ in db.search_sources(query_vec, source_type, limit)]
    seen = {s.id for s in found}
    chunk_ids = [c.source_id for c in db.search_chunks(query_vec, limit=20) if c.source_id not in seen]
    for source in db.get_sources(list(dict.fromkeys(chunk_ids))):
        if source.source_type == source_type:
            found.append(source)
    return found


def fallback(textbooks: list[Source], papers: list[Source]) -> Recommendation:
    """Plain vector ranking: candidates are already sorted nearest-first."""
    return Recommendation(textbooks[0] if textbooks else None, papers[:5], used_fallback=True)


def validate_pick(pick: dict, textbooks: list[Source], papers: list[Source]) -> Recommendation | None:
    """Turn Gemma's JSON into a Recommendation, or None if it is unusable."""
    books = {s.id: s for s in textbooks}
    paper_map = {s.id: s for s in papers}
    try:
        textbook = books.get(int(pick.get("textbook_id")))
    except (TypeError, ValueError):
        textbook = None
    if textbooks and textbook is None:
        return None
    reasons = {textbook.id: str(pick.get("textbook_reason", "")).strip()} if textbook else {}
    chosen = []
    for item in pick.get("papers") or []:
        try:
            paper = paper_map.get(int(item.get("id")))
        except (TypeError, ValueError, AttributeError):
            continue
        if paper and paper not in chosen:
            chosen.append(paper)
            reasons[paper.id] = str(item.get("reason", "")).strip()
    if len(chosen) < min(MIN_PAPERS, len(papers)):
        return None
    return Recommendation(textbook, chosen[:MAX_PAPERS], reasons)


def recommend(query: str) -> Recommendation:
    try:
        openalex.search(query)
    except Exception:  # offline or rate-limited: recommend from what's already in the library
        log.warning("OpenAlex search failed", exc_info=True)
    query_vec = embed.embed_query(query)
    textbooks = _candidates(query_vec, TEXTBOOK, TEXTBOOK_CANDIDATES)
    papers = _candidates(query_vec, RESEARCH_PAPER, PAPER_CANDIDATES)
    if not textbooks and not papers:
        return Recommendation(None, [])
    try:
        result = validate_pick(llm.pick_sources(query, textbooks, papers), textbooks, papers)
    except Exception:
        log.warning("Gemma pick failed", exc_info=True)
        result = None
    return result or fallback(textbooks, papers)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    rec = recommend(" ".join(sys.argv[1:]) or "intro to statistics")
    print("(fallback ranking)" if rec.used_fallback else "(picked by Gemma)")
    for source in ([rec.textbook] if rec.textbook else []) + rec.papers:
        print(f"[{source.source_type}] #{source.id} {source.title}\n    {rec.reasons.get(source.id, '')}")
