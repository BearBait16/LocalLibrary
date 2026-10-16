# 0002 — Phase 2: Sources
Status: Done
Date: 2026-10-16
Requested by: PLAN.md phase 2

## Goal
Fill the library with candidates: the OpenStax textbook catalog, open-access papers from OpenAlex,
and (optionally) web sources found by Gemini with Google Search. Every candidate is stored as an
un-downloaded source with a summary embedding, so the recommender can search it.

## Scope
In scope: sources/openstax.py, sources/openalex.py, sources/gemini_web.py, a CLI for each,
tests for OpenAlex abstract reconstruction and Gemini JSON parsing.
Out of scope: picking/ranking with Gemma (Phase 3), UI wiring (Phases 4–5).

## Files to change
- locallibrary/sources/openstax.py — `sync_catalog()`: CMS API
  `/apps/cms/api/v2/pages/?type=books.Book&fields=title,description,high_resolution_pdf_url,book_state`;
  keep `live` books that have a PDF URL; strip HTML from descriptions; upsert + batch-embed summaries.
  Falls back to `sources/openstax_seed.json` (a few books) if the API fails.
- locallibrary/sources/openstax_seed.json — fallback seed list
- locallibrary/sources/openalex.py — `search(query, limit=15)`: `search.semantic` (the keyword `search`
  matches words literally and gave poor results), filters `is_oa:true,has_abstract:true,type:article|review,language:en`,
  `per_page=50`; keep works with `best_oa_location.pdf_url` (`has_pdf_url` is not supported with
  semantic search); `rebuild_abstract(inverted_index)`; sends `api_key` if set and `mailto`.
- locallibrary/sources/gemini_web.py — `find_web_sources(query, limit=8)`: google-genai Interactions API
  (`client.interactions.create(model, input, tools=[{"type": "google_search"}], store=False)`), prompt asks
  for a JSON array of {title, url, type, reason}; lenient JSON parsing; returns [] without an API key.
  Returns (Source, reason) pairs.
- .env.example / .env — GEMINI_MODEL=gemini-3.8-flash (current docs' example model)
- tests/test_openalex.py, tests/test_gemini_parse.py

## Data / schema changes
None.

## Steps
1. openstax.py + seed + CLI; run sync.
2. openalex.py + CLI; abstract reconstruction test.
3. gemini_web.py + CLI; parsing test (live call only possible once a key is set).
4. Run each CLI for "intro to statistics".

## Checks
- [x] `python -m locallibrary.sources.openstax` syncs the catalog (~80 live books) with embeddings
- [x] `python -m locallibrary.sources.openalex "intro to statistics"` prints sensible papers with PDF URLs
- [x] `python -m locallibrary.sources.gemini_web "intro to statistics"` prints results, or says no key is set
- [x] pytest passes

## Risks / open questions
- OpenAlex without an API key: shared $0.10/day per IP; a semantic search costs $0.001 (~100/day).
  A free key (openalex.org/settings/api) raises this to $1/day. Semantic search is limited to 1 request/s.
- Gemini can't be tested live yet (no key). Whether structured output combines with google_search isn't
  documented, so the prompt asks for JSON and the parser extracts the first JSON array.
- Interactions are stored server-side by default; we pass store=False.
- Gemini may return redirect or hallucinated URLs; ingest will surface download errors to the user.

## Outcome
Built openstax.py (+ 10-book seed JSON), openalex.py, gemini_web.py, a CLI for each, and 4 new tests.

Deviations / notes:
- OpenAlex keyword `search` matched "intro" literally (syllabi titled "Intro…"), so the module uses
  `search.semantic`. That doesn't allow `has_pdf_url`, so PDF availability is filtered client-side
  from `best_oa_location.pdf_url` (about 18 of 30 results have one).
- Gemini uses the Interactions API (current docs; the SDK has `client.interactions`) with `store=False`.
- If a source was ingested by hand under the same URL, the OpenStax sync keeps its origin as `local`
  (the upsert only refreshes title, description and embedding).

Check results:
- openstax CLI: PASS. "Synced 84 OpenStax books" with summary embeddings.
- openalex CLI "intro to statistics": PASS. 15 open-access PDFs, mostly relevant (OpenIntro Statistics,
  Introductory Statistics with R, intro-stats papers), plus some course syllabi and book reviews.
- gemini_web CLI: PARTIAL. It prints "GEMINI_API_KEY is not set" as designed. The live call is
  untested until the user adds a key; the parser is covered by tests/test_gemini_parse.py.
- pytest: PASS (10 tests).
