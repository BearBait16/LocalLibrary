# 0006 — Phase 6: Research page
Status: Done
Date: 2026-10-16
Requested by: PLAN.md phase 6

## Goal
The reading view for a shelf book: a PDF/article viewer that resumes on the saved source and page,
a strip of the book's sources, a RAG question box with clickable page citations, and a Similar
Sources panel whose tiles can be dragged onto the viewer to add them to the book.

## Scope
In scope: ui/research_page.py, style additions, a citation-link helper test.
Out of scope: Highlighter and Notepad (disabled buttons with tooltip "Coming later").

## Files to change
- locallibrary/ui/research_page.py
  - top bar: Back to Library; checkable "RAG query" and "Similar Sources"; disabled Highlighter / Notepad
  - left strip: BookTiles (kind source) for the book's sources; click switches the viewer; current one highlighted
  - viewer (inside a DropZone of kind source): QPdfView (MultiPage, FitToWidth) for PDFs; QTextBrowser for
    web articles, showing one extracted section ("page") at a time; a nav bar with Prev / page box / Next
  - RAG panel: "Type your question here!" box + Ask; answer rendered as Markdown in a QTextBrowser with
    citation links `cite:<source_id>:<page>`; clicking one opens that source at that page. `rag.ask` runs in a Worker
  - Similar panel: tiles from `rag.similar_sources(current, exclude=book's sources)`, loaded in a Worker
    whenever the panel is shown or the source changes. Dropping one on the viewer ingests it if needed (Worker,
    status line), then `db.add_source_to_shelf_book`, refreshes the strip and switches to it
  - position saving: page/source changes start a 1 s single-shot timer → `db.save_position`; `on_leave()`
    (Back, page switch, window close) saves immediately
- locallibrary/ui/style.qss — research page objectNames
- tests/test_research_helpers.py — citation URL build/parse round trip
- locallibrary/rag.py — (added during this phase) merge citations from the same source + page

## Data / schema changes
None.

## Steps
1. Layout + viewer + source strip + load(shelf_book_id) resume.
2. Page tracking + debounced save.
3. RAG panel; Similar panel + drop-to-add.
4. Offscreen scripted check of resume; tests.

## Checks
- [x] Open a shelf book; it shows the saved source at the saved page
- [x] Change page, go back to the Library, reopen: resumes on the same source + page
- [x] RAG answer shows clickable citations that jump to the cited page
- [x] Similar Sources panel lists sources; dropping one adds it to the book and opens it
- [x] pytest passes

## Risks / open questions
- Small local DB reads/writes (load book, save position) run on the UI thread. They take milliseconds on localhost.
  All network/model/embedding work stays in Workers.
- Web articles are shown as their extracted text sections (clean and page-numbered like the chunks), not the raw
  saved HTML, so citations line up with what is on screen.
- QPdfView page tracking uses pageNavigator().currentPageChanged; this needs checking on PySide6 6.12.

## Outcome
Built ui/research_page.py, style additions and tests/test_research_helpers.py (3 tests).

Deviations / notes:
- QPdfView page tracking works on PySide6 6.12: pageNavigator().currentPageChanged fires when the user scrolls
  as well as on jump(), so scroll position is saved too.
- Web articles show one extracted section per "page" with Prev/Next, matching chunk page numbers.
- rag.ask now merges citations from the same source + page (they appeared twice when two passages came from one page).
- Side panels got fixed widths with horizontal scrolling off, so long titles wrap instead of being clipped.
- Workers started on the page carry a load_id, so late results are ignored after leaving or switching books.

Check results (offscreen run of the real MainWindow + backend, shelf book #2):
- Opens on the saved source/page: PASS (source 1, page 1 of 847)
- Resume: PASS. go_to_page(123) saved 123; scrolling to page 207 saved 207; Back to Library, then reopen →
  source 1, page 207 (navigator also at 207).
- Web article view: PASS (source 97 shown in ArticleView, 1 section)
- RAG: PASS. "What is a stratified sample?" gave a correct answer citing [3, 4]; the citation link cite:1:31
  jumped to page 31.
- Similar Sources: PASS. 8 tiles; dropping #40 Introductory Business Statistics 2e downloaded and ingested it,
  added it to the book ([1, 98, 97, 40]) and switched the viewer to it.
- pytest: PASS (28 tests).
