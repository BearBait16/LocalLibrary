# LocalLibrary — Build Plan

A Linux desktop app for guided research. The user types a topic. The app recommends a starting textbook and related papers from a local library, and can optionally find web sources with Gemini. The user drags in the sources they want and reads them in a research view with a RAG question box. Each research session is saved as a "book" on a shelf so it can be resumed later.

**How to use this plan:** work through the phases in order. At the end of each phase, run the checks listed for it and confirm they pass before moving on. Keep everything simple. The UI will be redesigned later, so make it functional and plain, not polished.

**Read `AGENTS.md` first.** It holds the standing rules for this repo, including the requirement below. It stays in force after this plan is finished.

**Plan file for every functional change:** before writing code for any functional change, create a numbered plan file in `docs/plans/` from `docs/plans/TEMPLATE.md`, fill it in, and mark it `Done` with the outcome when finished. During the initial build, **each phase below is its own functional change and gets its own plan file** (`0000-phase-0-environment.md`, `0001-phase-1-database-ingestion.md`, and so on), written at the start of that phase from its section in this document. After the build, every feature request, behavior change or bug fix from the user gets a new plan file the same way. Full rules are in `AGENTS.md`.

---

## Ground rules

- **Language:** Python 3.11+ for everything. GUI is **PySide6**. No web frontend, no FastAPI server; the GUI calls Python functions directly.
- **Simple objects:** plain `@dataclass` models and plain SQL via `psycopg` (v3). No ORM. Prefer module-level functions; use classes only for Qt widgets and dataclasses.
- **No AI frameworks:** no LangChain or LlamaIndex. Call Ollama and Gemini directly.
- **Never freeze the UI:** every network call, model call, download and embedding job runs in a background worker (`QThreadPool` + `QRunnable`, reporting back through Qt signals).
- **All styling in one place:** `locallibrary/ui/style.qss`. Widgets should not hard-code colors or fonts, so later UI changes are easy.
- **Config, not constants:** model names, paths, DB URL and API keys live in `config.py`, loaded from `.env`.
- **Ask before adding a dependency** not listed below.
- **Verify current APIs:** for Ollama, Gemini, OpenStax and OpenAlex, check the current official docs before writing client code rather than relying on memory.
- **Plan files are required:** no functional change without a plan file in `docs/plans/` (see `AGENTS.md`).

## Out of scope for this build

Highlighter and notepad (stretch goals: show them as disabled buttons only), video essays, free-programming-books, Windows/macOS support, installers/packaging.

---

## Tech stack

| Purpose | Choice |
|---|---|
| GUI | PySide6 (Qt Widgets; `QPdfView` for PDFs, `QTextBrowser` for web articles) |
| Database | PostgreSQL + pgvector, run with Docker Compose |
| DB driver | `psycopg[binary]` + `pgvector` Python package |
| Local LLM | Gemma via Ollama (`ollama` Python package). Model name in config; use the newest Gemma available in the Ollama library |
| Embeddings | `nomic-embed-text` via Ollama (768 dimensions) |
| Web source finding | Gemini via the `google-genai` SDK with Google Search grounding (optional) |
| PDF text extraction | PyMuPDF (`pymupdf`) |
| Web article extraction | `trafilatura` |
| HTTP | `httpx` |
| Config | `python-dotenv` |
| Tests | `pytest` |

### Model roles (important)

- **Gemma** always handles anything about the local library: choosing the best starting textbook and closest papers, and answering RAG questions in the research view.
- **Gemini** is only used when the user ticks "Also search the web" on the search page. It finds outside web sources. It never answers RAG questions.
- **nomic-embed-text** creates every vector. It requires task prefixes: use `search_document: ` before text being stored and `search_query: ` before user queries. Put this in one helper so it's never forgotten.

---

## Project layout

```
locallibrary/
  AGENTS.md         # standing rules for coding agents (provided)
  CLAUDE.md         # one line: @AGENTS.md
  PLAN.md           # this file
  pyproject.toml
  docker-compose.yml
  .env.example
  README.md
  docs/
    plans/
      TEMPLATE.md   # template for plan files
      0000-....md   # one numbered plan per functional change
  data/
    books/          # downloaded textbooks (PDF)
    resources/      # downloaded papers and web articles
    backgrounds/    # library background images
  locallibrary/
    __init__.py
    main.py         # starts the Qt app
    config.py
    models.py       # dataclasses
    db.py           # connection, schema setup, all SQL queries
    embed.py        # nomic-embed-text helpers (prefixes, batching)
    llm.py          # Gemma calls (pick sources, answer questions)
    ingest.py       # download -> extract -> chunk -> embed -> store
    recommend.py    # the search-page logic
    rag.py          # the research-page question logic
    sources/
      openstax.py   # textbook catalog sync
      openalex.py   # paper search
      gemini_web.py # optional web search
    workers.py      # QRunnable wrappers + signals
    ui/
      style.qss
      main_window.py    # QStackedWidget holding the three pages
      library_page.py
      search_page.py
      research_page.py
      widgets.py        # BookTile, DropZone, SourceCard
  tests/
```

---

## Data model

Four tables. Keep them this simple.

**sources** — every textbook, paper or article the app knows about, downloaded or not.
- `id` serial PK
- `title` text
- `source_type` text: `textbook` | `research_paper` | `web_article`
- `origin` text: `openstax` | `openalex` | `gemini` | `local`
- `url` text (where to download it)
- `local_path` text, nullable (set once downloaded)
- `description` text (abstract or blurb)
- `summary_embedding` vector(768) (embedding of title + description, so un-downloaded sources are searchable)
- `downloaded` boolean default false
- unique on `url`

**chunks** — text passages from downloaded sources.
- `id` serial PK
- `source_id` FK → sources
- `page` int (1-based page for PDFs; section number for web articles)
- `text` text
- `embedding` vector(768)
- HNSW index on `embedding` (cosine)

**shelf_books** — a saved research session.
- `id` serial PK
- `title` text (defaults to the research query)
- `query` text
- `created_at` timestamp
- `last_source_id` FK → sources, nullable
- `last_page` int default 1

**shelf_book_sources** — which sources belong to a shelf book.
- `shelf_book_id` FK, `source_id` FK, `position` int; PK on the pair

Matching dataclasses in `models.py`: `Source`, `Chunk`, `ShelfBook`. `db.py` creates the extension, tables and index on startup if they don't exist.

Folder rule: textbooks save to `data/books/`, papers and web articles to `data/resources/`.

---

## Phase 0 — Environment

0. **Agent and plan files first:**
   - Keep the provided `AGENTS.md` at the repo root.
   - Create `CLAUDE.md` containing only the line `@AGENTS.md`, so Claude Code loads the same rules automatically.
   - Create `docs/plans/TEMPLATE.md` with exactly these sections:
     ```markdown
     # NNNN — Title
     Status: Planned | In progress | Done
     Date:
     Requested by: (user request in their words, or "PLAN.md phase N")

     ## Goal
     What this change does and why, in 2–3 sentences.

     ## Scope
     In scope:
     Out of scope:

     ## Files to change
     - path — what changes

     ## Data / schema changes
     None, or the exact changes.

     ## Steps
     1.

     ## Checks
     - [ ] How to verify each part works

     ## Risks / open questions

     ## Outcome
     (Filled in when done: what was built, deviations from the plan, check results.)
     ```
   - Write `docs/plans/0000-phase-0-environment.md` from this phase before doing the steps below.
1. `docker-compose.yml` running the official `pgvector/pgvector` Postgres image, with a named volume and port 5432.
2. `.env.example` with `DATABASE_URL`, `OLLAMA_HOST`, `GEMMA_MODEL`, `EMBED_MODEL=nomic-embed-text`, `GEMINI_API_KEY` (optional), `GEMINI_MODEL`, `DATA_DIR`.
3. `pyproject.toml` with the dependencies above.
4. README section: install Docker and Ollama, `ollama pull` the Gemma model and `nomic-embed-text`, `docker compose up -d`, create a venv, install, run.

**Check:** `AGENTS.md`, `CLAUDE.md` and `docs/plans/TEMPLATE.md` exist and `0000` is filled in; `docker compose up -d` works; a small script connects to Postgres, enables `vector`, and gets a 768-length embedding back from Ollama.

## Phase 1 — Database, embeddings, ingestion

1. `config.py`, `models.py`, `db.py` (schema setup + query functions: add/get/update source, add chunks, vector search over chunks, vector search over source summaries, shelf book CRUD).
2. `embed.py`: `embed_documents(texts) -> list[vector]` and `embed_query(text) -> vector`, applying the nomic prefixes and batching.
3. `ingest.py`:
   - `download(source)` saves the file to the right folder and sets `local_path`.
   - `extract(source)` returns `[(page, text)]`: PyMuPDF for PDFs, trafilatura for HTML (split into sections of ~2,000 characters, numbered as pages).
   - `chunk(pages)`: ~1,500-character chunks with ~200-character overlap, never crossing a page boundary, each tagged with its page.
   - `ingest(source, progress_callback)`: download → extract → chunk → embed → store → mark `downloaded = true`.
   - CLI: `python -m locallibrary.ingest <path-or-url>` for manual testing.

**Check:** ingest one real OpenStax PDF; chunks appear with correct page numbers; a vector search for a phrase from page N returns a chunk from page N near the top. Add pytest tests for `chunk()`.

## Phase 2 — Sources

1. `sources/openstax.py`: `sync_catalog()` fetches the list of OpenStax books with their titles, descriptions and PDF URLs (check OpenStax's current public API; fall back to a small seed JSON file if needed), upserts them as un-downloaded `textbook` sources, and embeds title + description into `summary_embedding`. Run on first launch and from a "Refresh catalog" menu item.
2. `sources/openalex.py`: `search(query, limit=15)` queries the OpenAlex works API, keeps only works with an open-access PDF URL, rebuilds abstracts from OpenAlex's inverted-index format, and upserts them as `research_paper` sources with summary embeddings. Follow OpenAlex's current authentication/etiquette rules (API key or contact email in config).
3. `sources/gemini_web.py`: `find_web_sources(query, limit=8)` calls Gemini with Google Search grounding and asks for JSON: title, URL, type, one-line reason. Upsert as `web_article` sources (origin `gemini`). If no API key is set, return an empty list and the UI hides the option.

**Check:** CLI calls for each print sensible results for "intro to statistics".

## Phase 3 — Recommendation and RAG logic

1. `recommend.py` → `recommend(query) -> Recommendation`:
   - Run `openalex.search(query)` to refresh candidates.
   - Vector-search source summaries (and chunks of downloaded sources) for the top ~5 textbooks and ~15 papers.
   - Ask Gemma (`llm.pick_sources`) to choose the single best starting textbook and the 3–6 closest papers, returning JSON with source IDs and a one-line reason each. Validate the IDs; fall back to plain vector ranking if Gemma's JSON is bad.
   - `Recommendation` dataclass: `textbook`, `papers`, `reasons`.
2. `rag.py` → `ask(question, source_ids, limit=6) -> Answer`:
   - Embed the question, vector-search chunks limited to the shelf book's sources.
   - Gemma answers briefly using only those chunks, pointing the reader to where to look.
   - `Answer` dataclass: `text`, `citations` (list of source id + page + short snippet).
3. `rag.py` → `similar_sources(source_id, limit=8)`: nearest sources by summary embedding, excluding the current one.

**Check:** CLI runs of `recommend` and `ask` give reasonable output with real citations.

## Phase 4 — UI shell

1. `main.py` creates the app, loads `style.qss`, ensures the DB schema and first catalog sync (in a worker with a status bar message).
2. `main_window.py`: a `QStackedWidget` with Library, Search and Research pages, plus navigation methods (`show_library()`, `show_search()`, `open_research(shelf_book_id)`).
3. `workers.py`: a generic `Worker(fn, *args)` QRunnable that emits `finished(result)`, `failed(message)` and `progress(int, str)`.
4. `widgets.py`:
   - `BookTile`: a draggable tile showing a title (used for shelf books and sources). Drag data carries a type (`shelf_book` or `source`) and an ID.
   - `DropZone`: accepts drops of a given type and emits `dropped(id)`.
   - `SourceCard`: a draggable card with title, type and reason.

**Check:** the app opens, the three pages switch, and dragging a test tile onto a drop zone fires the signal.

## Phase 5 — Search page

Layout follows the design: heading "RESEARCH TIME! What would you like to learn about?", a query box, an "Also search the web with Gemini" checkbox (hidden without an API key), and a Search button.

1. On search, run `recommend()` and, if checked, `find_web_sources()` in workers; show a busy indicator.
2. Show two columns of `SourceCard`s: **"Here's what you got"** (Gemma's textbook + papers, textbook first) and **"Here's what Gemini found"** (only if the web search ran).
3. A **"Drag here!"** `DropZone` collects the sources the user wants. Dropping a not-yet-downloaded source starts `ingest()` in a worker; the card shows progress and then "Ready". Allow removing a card from the zone.
4. **Done** button (enabled once at least one source is ready): creates a `ShelfBook` with the query as title, links the chosen sources in order, sets `last_source_id` to the textbook (or first source), and opens the Research page.
5. Errors (download failed, Ollama not running, Gemini error) show a clear inline message, never a crash.

**Check:** full flow from query to Research page with a downloaded textbook and paper.

## Phase 6 — Research page

Top bar: **Back to Library**, **RAG query** toggle, **Similar Sources** toggle, and disabled **Highlighter** / **Notepad** buttons (tooltip: "Coming later").

1. Main viewer: `QPdfView` for PDFs, `QTextBrowser` for web articles. Opens the shelf book's `last_source_id` at `last_page`.
2. Left strip listing the shelf book's sources as `BookTile`s; clicking one switches the viewer.
3. **RAG query** toggle shows a question box ("Type your question here!"). Answers appear below with clickable citations; clicking one opens that source at that page.
4. **Similar Sources** toggle shows a right side panel of `BookTile`s from `similar_sources()`. Dragging one onto the viewer (a `DropZone`) downloads it if needed, adds it to the shelf book, and switches the viewer to it.
5. Save `last_source_id` and `last_page` whenever the source or page changes (debounced) and when leaving the page.

**Check:** open a shelf book, change page, go back to the library, reopen it: it resumes on the same source and page.

## Phase 7 — Library page

1. Full-page background image (stored path in a small settings table or JSON file in `data/`; default plain background). "Change background…" button opens a file picker and copies the image into `data/backgrounds/`.
2. A shelf showing every `ShelfBook` as a `BookTile` (book-spine style, title rotated is fine but optional).
3. An "Open" `DropZone`: dragging a shelf book onto it opens the Research page at its saved position. Double-clicking a book does the same.
4. A **New research** button goes to the Search page.
5. Right-click a book: rename, delete (confirm first; deletes the shelf book only, not the downloaded files).

**Check:** create two shelf books, restart the app, both are on the shelf and each resumes correctly.

## Phase 8 — Finish

1. Run every phase's checks again end to end.
2. pytest tests for chunking, the nomic prefix helper, OpenAlex abstract reconstruction, and the DB query functions (against the Docker DB).
3. Update the README with setup, usage and known limitations.
4. Confirm every phase's plan file in `docs/plans/` is marked `Done` with its outcome filled in, and update the Commands and Layout sections of `AGENTS.md` to match what was actually built.
5. Short summary for the user of what was built, anything that didn't work as planned, and suggested next steps.
