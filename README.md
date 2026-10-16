# LocalLibrary

A Linux desktop app for guided research. Type a topic, get a starting textbook and related papers
from your local library (plus optional web sources from Gemini), drag in what you want, and read it
in a research view with a RAG question box. Each session is saved as a "book" on your shelf and
reopens where you left off.

Everything runs locally: Postgres + pgvector in Docker, and Gemma + nomic-embed-text in Ollama.
The network is only used to fetch the OpenStax catalog, search OpenAlex, download the sources you
pick, and (optionally) ask Gemini for web sources.

## Setup (Arch Linux; adapt the package commands for your distro)

1. **Docker** (runs Postgres + pgvector). On Arch, Compose and buildx are separate packages:
   ```bash
   sudo pacman -S docker docker-compose docker-buildx
   sudo systemctl enable --now docker
   sudo usermod -aG docker $USER   # log out and back in afterwards
   ```
2. **Ollama** (local models), from https://ollama.com/download, then:
   ```bash
   ollama serve                     # if not already running as a service
   ollama pull gemma4:e4b
   ollama pull nomic-embed-text
   ```
3. **Database:**
   ```bash
   docker compose up -d
   ```
4. **Python environment** (Python 3.11+; tested on 3.14 with [uv](https://docs.astral.sh/uv/)):
   ```bash
   uv venv .venv && source .venv/bin/activate
   uv pip install -e '.[dev]'
   cp .env.example .env             # then edit .env (see Configuration)
   python scripts/smoke_check.py    # should print the pgvector version and "embedding length 768"
   ```

## Run

```bash
docker compose up -d
source .venv/bin/activate
python -m locallibrary.main
```

The first launch creates the database tables and downloads the OpenStax textbook catalog (about 85
books, titles and descriptions only) in the background. The status bar shows progress.

## Using it

1. **Library** (home): your saved research books stand on a bookcase of 4 shelves, each with its
   own spine color and edge design. Press **New research** to start. Drag a book onto **Open** (or
   double-click it) to continue it. Drag books along a shelf or onto another shelf to rearrange them;
   a gold marker shows where they'll land. Right-click a book to rename it, **Change look…** (color
   and edge design), or delete it (deleting keeps the downloaded files). **Change background…** sets
   a picture behind the bookcase. Each shelf holds 10 books, so the bookcase holds 40. When it's
   full, delete a book to make room for new research.
2. **Search**: type a topic and press **Search**. Gemma picks a starting textbook and related
   open-access papers, each with a one-line reason. If a Gemini key is set, tick **Also search the
   web with Gemini** for outside sources. Drag the sources you want into **Drag here!** (or
   double-click them). Sources that aren't downloaded yet are downloaded and indexed, with progress
   shown on the card. Press **Done** to save the book and start reading.
3. **Research**: read PDFs (or web articles, one section per page). Each source in the left strip
   shows its cover and a type badge, and the "Now reading" bar above the page says which source and
   page you're on. Your source and page are saved as you go. **RAG query** opens a question box: answers come only from this book's sources and
   link to the pages to look at. **Similar Sources** lists related material; drag one onto the page
   to add it to the book.

The first search or question after starting can take about a minute while Ollama loads Gemma.
After that, answers take a few seconds.

## Configuration (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | local Docker DB | Postgres connection string |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server |
| `GEMMA_MODEL` | `gemma4:e4b` | Model for recommendations and RAG answers |
| `GEMMA_NUM_CTX` | `8192` | Gemma context window (Ollama's default 4096 is too small) |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model (768 dimensions) |
| `GEMINI_API_KEY` | empty | Optional; enables "Also search the web with Gemini" |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Gemini model for web search |
| `OPENALEX_EMAIL` | empty | Contact email sent to OpenAlex |
| `OPENALEX_API_KEY` | empty | Optional free key from https://openalex.org/settings/api (raises the daily budget) |
| `DATA_DIR` | `./data` | Downloads (`books/`, `resources/`), backgrounds, `settings.json` |

## Command-line tools

```bash
python -m locallibrary.ingest <path-or-url> [--type textbook|research_paper|web_article] [--title T]
python -m locallibrary.sources.openstax              # refresh the textbook catalog
python -m locallibrary.sources.openalex "<topic>"    # find open-access papers
python -m locallibrary.sources.gemini_web "<topic>"  # web sources (needs GEMINI_API_KEY)
python -m locallibrary.recommend "<topic>"
python -m locallibrary.rag <source_id,...> "<question>"
pytest                                               # DB tests use a separate locallibrary_test database
```

## Known limitations

- **Some papers can't be downloaded.** Several publishers (e.g. Taylor & Francis, PhilPapers) block
  automated downloads even for open-access PDFs. The card shows the error; pick another source.
- **OpenAlex budget:** without an API key, everyone on your IP address shares a small free daily
  budget (about 100 searches). A free key gives you your own, larger budget.
- **gemma4:e4b is a small model.** It sometimes recommends course syllabi or book reviews, and its
  answers are brief. Citations always point to real retrieved pages. A larger Gemma
  (`GEMMA_MODEL`) gives better results if you have the VRAM.
- **Gemini web search has not been tested live**, because it was built without an API key. The reply
  parsing is unit-tested.
- The bookcase is fixed at 4 shelves × 10 books (`SHELF_COUNT` / `SHELF_CAPACITY` in `config.py`).
- Highlighter and Notepad are placeholders ("Coming later"). Linux only; no installer.
- Embedding a full textbook takes a few minutes the first time you add it.
