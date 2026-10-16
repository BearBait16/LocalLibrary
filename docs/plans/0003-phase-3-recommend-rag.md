# 0003 — Phase 3: Recommendation and RAG logic
Status: Done
Date: 2026-10-16
Requested by: PLAN.md phase 3

## Goal
The two core brains of the app, with no UI yet. `recommend(query)` picks a starting textbook and
3–6 related papers from the local library using vector search and Gemma. `ask(question, source_ids)`
answers questions from a shelf book's passages, with page citations. `similar_sources()` finds neighbors.

## Scope
In scope: llm.py, recommend.py, rag.py, CLIs for recommend and ask, tests for validation/fallback.
Out of scope: UI (Phase 4+), Gemini (web sources stay in gemini_web.py).

## Files to change
- locallibrary/config.py, .env.example, .env — `GEMMA_NUM_CTX` (default 8192; Ollama's default 4096 is too small)
- locallibrary/llm.py — `pick_sources(query, textbooks, papers)` → {textbook_id, papers[{id, reason}], textbook_reason}
  using Ollama structured output (JSON schema in `format`), thinking left on (think=False picked wrong
  answers in testing); `answer(question, chunks, titles)` → text with [n] passage markers.
- locallibrary/recommend.py — `Recommendation` dataclass (textbook, papers, reasons: {source_id: reason});
  `recommend(query)`: openalex.search (errors tolerated, so the library still works offline), vector
  search of textbook summaries (top 5) and paper summaries (top 15), plus the best chunk hits of downloaded
  sources folded in; Gemma picks; IDs validated against the candidates; fallback to vector ranking
  (1 textbook + 5 papers) if Gemma fails or returns bad IDs.
- locallibrary/rag.py — `Answer` dataclass (text, citations: list[Citation(source_id, page, snippet)]);
  `ask(question, source_ids, limit=6)`; `similar_sources(source_id, limit=8)`.
- tests/test_recommend.py — validation and fallback logic with fake candidates (no network)
- locallibrary/ingest.py + tests/test_chunk.py — (added during this phase) chunks also start on a word boundary

## Data / schema changes
None. Adds `db.get_summary_embedding(source_id)`, used by similar_sources.

## Steps
1. Config option, llm.py.
2. recommend.py with `_validate_pick()` as a pure function; tests.
3. rag.py; citations only for passages Gemma cited ([n]); if it cites none, all retrieved passages are listed.
4. CLIs: `python -m locallibrary.recommend "<query>"`, `python -m locallibrary.rag <source_id,...> "<question>"`.

## Checks
- [x] `recommend "intro to statistics"` picks a sensible textbook (Introductory Statistics) + papers with reasons
- [x] `ask` on source 1 gives a reasonable answer with real page citations (verified against the PDF)
- [x] similar_sources(1) returns related sources
- [x] pytest passes

## Risks / open questions
- gemma4:e4b's first call takes about 70 s to load the model; later calls take a few seconds. The UI shows a busy indicator.
- A small model may cite passages loosely; citations come from the retrieved chunks, so page numbers stay real.

## Outcome
Built llm.py, recommend.py, rag.py (with CLIs), db.get_summary_embedding, the GEMMA_NUM_CTX config, and 6 new tests.

Deviations / notes:
- Fixed in ingest.chunk(): overlapping chunks could start mid-word, which showed up as snippets like
  "mbers of the population…". The next chunk now starts at the next space. Added a test, and re-ingested
  source 1 (1,570 chunks).
- `Recommendation.used_fallback` flags when vector ranking was used instead of Gemma.
- `similar_sources` takes an optional `exclude_ids` so the research page can hide sources already in the book.
- OpenAlex errors are logged and ignored in `recommend()`, so search still works offline from the existing library.

Check results:
- recommend "intro to statistics": PASS. Gemma picked Introductory Statistics 2e + 5 papers with reasons
  (34 s including the cold model load). It still picked 2 course syllabi despite being told to skip them;
  a gemma4:e4b limit, acceptable.
- ask(source 1, "population vs sample"): PASS. A correct, brief answer citing [2], [4], [5], [6]. Cited
  pages 56, 32, 763 and 22 were checked against the PDF and contain the cited text. 6.8 s warm.
- similar_sources(1): PASS. Introductory Business Statistics 2e, Statistics (high school), intro-stats papers;
  some weaker hits (Elementary Algebra 2e, Introduction to Business 2e).
- pytest: PASS (17 tests).
