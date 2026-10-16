# AGENTS.md — LocalLibrary

Instructions for any coding agent working in this repository. Read this before every task.

## What this project is

LocalLibrary is a Linux desktop research app written in Python with a PySide6 GUI. The user enters a topic; the app recommends a starting textbook and related papers from a local library (with optional web sources from Gemini), the user drags in the sources they want, and reads them in a research view with a RAG question box. Each session is saved as a "book" on a shelf and can be resumed where the user left off.

`PLAN.md` is the original build plan. Once the initial build is done, this file is the standing reference.

## Required: a plan file for every functional change

Before changing code for any **functional change**, write a plan file. A functional change is anything that adds, removes or changes behavior: a new feature, a UI change that changes what a control does, a bug fix, a schema change, a new dependency, or a refactor that moves logic between modules.

Not functional (no plan file needed): pure styling in `style.qss`, wording of labels, comments, typo fixes, and formatting.

**Rules:**
1. Create `docs/plans/NNNN-short-name.md`, where `NNNN` is the next number in sequence (`0001`, `0002`, …), by copying `docs/plans/TEMPLATE.md`.
2. Fill in every section before writing code. Set `Status: Planned`.
3. Tell the user the plan file was created and summarize it in a few lines.
4. Set `Status: In progress` when you start, and update the plan if the approach changes along the way.
5. When finished, set `Status: Done`, fill in **Outcome**, and record the result of every check.
6. One functional change per plan file. If a request contains several unrelated changes, write one file for each.
7. Never delete old plan files. They are the project history.

## Commands

```bash
docker compose up -d                 # start Postgres + pgvector
ollama serve                         # if Ollama isn't already running
source .venv/bin/activate
python -m locallibrary.main          # run the app
python -m locallibrary.ingest <path-or-url> [--type textbook|research_paper|web_article] [--title T]
python scripts/smoke_check.py        # Postgres + pgvector + Ollama embedding reachable?
python -m locallibrary.sources.openstax              # sync the OpenStax catalog
python -m locallibrary.sources.openalex "<topic>"    # search open-access papers
python -m locallibrary.sources.gemini_web "<topic>"  # web sources (needs GEMINI_API_KEY)
python -m locallibrary.recommend "<topic>"           # what the search page would recommend
python -m locallibrary.rag <source_id,...> "<question>"   # RAG answer with citations
pytest                               # run tests (DB tests use a separate locallibrary_test database)
```

Keep this section accurate when commands change.

## Layout

```
AGENTS.md, CLAUDE.md, PLAN.md, README.md
docs/plans/          # one plan file per functional change
data/books/          # downloaded textbooks
data/resources/      # downloaded papers and web articles
data/backgrounds/    # library background images
data/thumbnails/     # cached source cover images (safe to delete)
data/settings.json   # app preferences (library background); gitignored
scripts/smoke_check.py
docker-compose.yml, pyproject.toml, .env.example
locallibrary/
  config.py models.py db.py embed.py llm.py ingest.py
  recommend.py rag.py workers.py main.py looks.py thumbnails.py
  sources/  openstax.py openstax_seed.json openalex.py gemini_web.py
  ui/       style.qss main_window.py library_page.py
            search_page.py research_page.py widgets.py look_dialog.py
tests/               # conftest.py has the test-DB fixture
```

## Conventions

- **Python 3.11+, PySide6.** No web frontend and no HTTP server; the GUI calls Python functions directly.
- **Simple objects:** plain `@dataclass` models and plain SQL with `psycopg` v3. No ORM. Prefer module-level functions; use classes only for Qt widgets and dataclasses.
- **All SQL lives in `db.py`.** Other modules call its functions.
- **No AI frameworks** (no LangChain or LlamaIndex). Call Ollama and Gemini directly.
- **Never block the UI thread.** Network calls, model calls, downloads and embedding run through `workers.py`.
- **All styling in `locallibrary/ui/style.qss`.** Widgets don't hard-code colors or fonts; give widgets `objectName`s so the stylesheet can target them.
- **Config in `config.py`**, loaded from `.env`. No hard-coded model names, paths or keys.
- **Ask the user before adding a dependency.**
- **Check current docs** for Ollama, Gemini, OpenStax and OpenAlex before writing or changing client code.

## Model roles (don't mix these up)

- **Gemma (via Ollama)** handles everything about the local library: picking the starting textbook and closest papers, and answering RAG questions.
- **Gemini** is only used when the user ticks "Also search the web" on the search page. It finds outside web sources and nothing else.
- **nomic-embed-text** makes every vector (768 dimensions). Always go through `embed.py`, which adds the required `search_document: ` / `search_query: ` prefixes.

## Out of scope unless the user asks

Highlighter and notepad (shown as disabled buttons), video essays, free-programming-books, Windows/macOS support, packaging.

## Definition of done

A change is done when its plan file is marked `Done` with the outcome filled in, its checks pass, `pytest` passes, the app starts and the changed flow works by hand, and this file and the README are updated if commands, layout or conventions changed.
