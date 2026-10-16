# 0001 — Phase 1: Database, embeddings, ingestion
Status: Done
Date: 2026-10-16
Requested by: PLAN.md phase 1

## Goal
Build the data layer: config loading, dataclass models, the Postgres schema and all SQL query
functions, the nomic-embed-text helper with its required prefixes, and the ingestion pipeline
(download → extract → chunk → embed → store). Later phases use these to search and read sources.

## Scope
In scope: config.py, models.py, db.py, embed.py, ingest.py (+ CLI), tests for chunk().
Out of scope: source catalogs (Phase 2), Gemma calls (Phase 3), any UI.

## Files to change
- locallibrary/__init__.py — package marker
- locallibrary/config.py — load .env into a frozen `Config` dataclass; data folder paths
- locallibrary/models.py — `Source`, `Chunk`, `ShelfBook` dataclasses
- locallibrary/db.py — `connect()`, `init_schema()`, source add/upsert/get/update, `add_chunks`,
  `search_chunks` (optionally limited to source IDs), `search_sources` (summary embeddings, optional
  type filter), shelf-book CRUD + source linking
- locallibrary/embed.py — `embed_documents(texts)`, `embed_query(text)`; prefixes + batching
- locallibrary/ingest.py — `download`, `extract`, `chunk`, `ingest`, CLI `python -m locallibrary.ingest`
- tests/test_chunk.py — chunk size, overlap, never crossing a page boundary, page tags

## Data / schema changes
Created by `db.init_schema()` (idempotent):
- `CREATE EXTENSION IF NOT EXISTS vector`
- `sources(id serial pk, title, source_type check in (textbook,research_paper,web_article),
  origin check in (openstax,openalex,gemini,local), url unique, local_path, description,
  summary_embedding vector(768), downloaded bool default false)`
- `chunks(id serial pk, source_id fk → sources on delete cascade, page int, text, embedding vector(768))`
  + HNSW index `vector_cosine_ops` on `embedding`, btree on `source_id`
- `shelf_books(id serial pk, title, query, created_at timestamptz default now(),
  last_source_id fk → sources on delete set null, last_page int default 1)`
- `shelf_book_sources(shelf_book_id fk on delete cascade, source_id fk on delete cascade,
  position int, primary key (shelf_book_id, source_id))`

## Steps
1. config.py and models.py.
2. db.py: schema plus query functions, using the pgvector psycopg adapter (`register_vector`).
3. embed.py: batches of 32; `search_document: ` / `search_query: ` prefixes.
4. ingest.py: PDF detection by content type / magic bytes; PyMuPDF per page; trafilatura for HTML,
   split into ~2,000-char sections; 1,500-char chunks with 200 overlap within a page; ingesting a
   local path copies the file into the right folder with origin `local`; deletes any old chunks
   before re-ingesting.
5. tests/test_chunk.py; run pytest.
6. Ingest a real OpenStax PDF and run a vector search for a phrase from a known page.

## Checks
- [x] pytest passes for chunk()
- [x] Ingest one real OpenStax PDF; chunks have correct page numbers
- [x] A vector search for a phrase from page N returns a page-N chunk near the top

## Risks / open questions
- OpenStax PDFs are large (often 1,000+ pages), so embedding takes several minutes on the local GPU.
- Some PDF pages have no text (images only); skip empty pages.
- Re-ingesting replaces the source's chunks rather than duplicating them.

## Outcome
Built config.py, models.py, db.py, embed.py, ingest.py (+ CLI) and tests/test_chunk.py as planned.

Deviations / notes:
- Vectors are passed as `pgvector.Vector` (no numpy dependency needed).
- `db.connect()` opens a short-lived connection per call. That's simple and thread-safe for workers.
- `search_chunks` sets `hnsw.iterative_scan = relaxed_order` so source-filtered searches still fill the limit.
- `replace_chunks` deletes old chunks in the same transaction, so re-ingesting never duplicates.
- Extra helpers for later phases: get_sources (ordered), count_sources, count_chunks, add_source_to_shelf_book, save_position.
- The OpenStax CMS API (`/apps/cms/api/v2/pages/?type=books.Book&fields=...high_resolution_pdf_url,book_state`)
  was used to find the test PDF; Phase 2 will reuse it.

Check results:
- pytest: PASS (6 tests in tests/test_chunk.py)
- Ingest real OpenStax PDF: PASS. "Introductory Statistics 2e" (847 pages) → 1,573 chunks covering
  845 pages (2 blank). Every sampled phrase was stored under its own page (one phrase also appears on page 181).
- Vector search for a phrase from page N: PASS. 6/8 random pages ranked in the top 5 (4 at rank 1 or 2), 7/8 in the top 10.
  The 1 miss (page 133, a generic sentence on grouped means) is the same under an exact sequential scan,
  so it comes from embedding similarity across chapters, not from the index or the chunking.
