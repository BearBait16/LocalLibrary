# 0000 — Phase 0: Environment
Status: Done
Date: 2026-10-16
Requested by: PLAN.md phase 0 ("Run the plan.")

## Goal
Set up the project skeleton and local services: agent/plan files, Postgres + pgvector in Docker,
Python packaging, an example env file and README setup steps. This gives every later phase a
working database, Ollama models and a virtualenv to build on.

## Scope
In scope: CLAUDE.md, docs/plans/TEMPLATE.md, docker-compose.yml, .env.example, .env (local, not
committed), pyproject.toml, .gitignore, README setup section, data/ folders, a smoke-check script.
Out of scope: any application code (Phase 1+).

## Files to change
- CLAUDE.md — single line `@AGENTS.md`
- docs/plans/TEMPLATE.md — plan template from PLAN.md
- docker-compose.yml — `pgvector/pgvector` Postgres image, named volume, port 5432
- .env.example — DATABASE_URL, OLLAMA_HOST, GEMMA_MODEL, EMBED_MODEL, GEMINI_API_KEY, GEMINI_MODEL, OPENALEX_EMAIL, DATA_DIR
- .env — local copy (GEMMA_MODEL=gemma4:e4b, OPENALEX_EMAIL set, GEMINI_API_KEY empty)
- pyproject.toml — deps: PySide6, psycopg[binary], pgvector, ollama, google-genai, pymupdf, trafilatura, httpx, python-dotenv; dev: pytest
- .gitignore — .venv, .env, data contents, caches
- README.md — install/run steps
- scripts/smoke_check.py — connects to Postgres, enables `vector`, embeds a string via Ollama, prints length

## Data / schema changes
None (only `CREATE EXTENSION IF NOT EXISTS vector` in the smoke check).

## Steps
1. Write CLAUDE.md, TEMPLATE.md and this file.
2. Write docker-compose.yml, .env.example, .env, pyproject.toml, .gitignore, README.
3. User installs Docker (needs sudo); `docker compose up -d`.
4. Start Ollama; `ollama pull gemma4:e4b` and `ollama pull nomic-embed-text`.
5. `uv venv --python 3.11+ .venv` and install the project in editable mode with dev extras.
6. Run the smoke check.

## Checks
- [x] AGENTS.md, CLAUDE.md, docs/plans/TEMPLATE.md exist; 0000 filled in
- [x] `docker compose up -d` starts Postgres and it accepts connections
- [x] smoke check enables `vector` and gets a 768-length embedding from Ollama

## Risks / open questions
- Docker was not installed; the user installed it with sudo. On Arch, Compose and buildx are separate packages (docker-compose, docker-buildx); docker alone gives "unknown shorthand flag" errors for `docker compose -d`.
- System Python is 3.14; PySide6 / PyMuPDF wheels may lag. If so, use uv to pin a 3.12 or 3.13 venv.
- 8 GB VRAM: chose gemma4:e4b (user decision) so it fits alongside nomic-embed-text.
- Gemini key not available yet; feature stays hidden until set.

## Outcome
Built: CLAUDE.md, docs/plans/TEMPLATE.md, docker-compose.yml (pgvector/pgvector:pg17, volume
`pgdata`, port 5432), .env.example + local .env, pyproject.toml, .gitignore, README setup section,
scripts/smoke_check.py, data/{books,resources,backgrounds}/.

Deviations:
- Python 3.14 works: every dependency installed from wheels (PySide6 6.12.0, PyMuPDF 1.28.2), so no
  version pin was needed. The venv was created with uv.
- Added OPENALEX_EMAIL / OPENALEX_API_KEY to the env file for OpenAlex's polite-pool rules.
- gemma4:e4b is 6.6 GB on disk, larger than expected for 8 GB VRAM. It may run partly on the CPU
  when nomic-embed-text is loaded too. Revisit if responses are slow.
- Until the user logs in again, the shell has no docker-group access; run compose with sudo or newgrp.

Check results:
- AGENTS.md, CLAUDE.md, TEMPLATE.md exist; 0000 filled in: PASS
- `docker compose up -d`: PASS (container locallibrary-db listening on 5432)
- smoke check: PASS ("Postgres OK, pgvector 0.8.7", "Ollama OK, embedding length 768")
