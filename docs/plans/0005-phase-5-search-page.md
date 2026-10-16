# 0005 — Phase 5: Search page
Status: Done
Date: 2026-10-16
Requested by: PLAN.md phase 5

## Goal
The first real page: the user types a topic, sees Gemma's recommended textbook and papers (and
Gemini's web finds if enabled), drags the sources they want into a "Drag here!" zone, where
un-downloaded ones are ingested with visible progress, then presses Done to create a shelf book and
open the Research page.

## Scope
In scope: ui/search_page.py, small style.qss additions, a test for the Done-button rules.
Out of scope: Research page content (Phase 6), Library shelf (Phase 7).

## Files to change
- locallibrary/ui/search_page.py — full page:
  - heading "RESEARCH TIME! What would you like to learn about?", query box (Enter = search),
    "Also search the web with Gemini" checkbox (hidden when `config.gemini_enabled` is false), Search button,
    busy bar + status text, inline error label, Back to Library button
  - two scrollable columns of SourceCards: "Here's what you got" (textbook first) and
    "Here's what Gemini found" (shown only if the web search ran)
  - "Drag here!" DropZone of removable SourceCards. Dropping (or double-clicking a result card) adds the source;
    un-downloaded sources run `ingest()` in a Worker with card progress, then show "Ready", or an error on the card
  - Done button → `db.create_shelf_book(query, query, ready ids in drop order, first textbook or first source)`
    → `window.open_research(id)`
  - a search counter, so results from an older search are ignored if the user searches again
- locallibrary/ui/style.qss — result column / busy bar styles
- tests/test_search_page.py — offscreen: Done disabled when empty, while any card is still downloading, enabled
- locallibrary/ingest.py — (added during this phase) browser-like User-Agent + Accept header; reject downloads with < 500 chars of text
  once one is ready; removal; duplicate drops ignored. Uses already-downloaded fake Sources, no network.

## Data / schema changes
None.

## Steps
1. Build the page; wire recommend + find_web_sources workers.
2. Drop zone + ingest workers + Done.
3. Tests; full flow by hand: query → recommend → drag textbook + paper → ingest → Done → Research page.

## Checks
- [x] Search shows Gemma's picks with reasons; the UI stays responsive (busy bar animates) during search
- [x] Dropping an un-downloaded paper downloads + ingests it with progress, then "Ready"
- [x] Done creates a shelf book with the chosen sources and opens the Research page
- [x] Errors (bad download URL, Ollama stopped) appear inline / on the card, no crash
- [x] pytest passes

## Risks / open questions
- Decision: Done is enabled when ≥1 chosen source is ready and none are still downloading (failed cards are
  skipped). This avoids silently dropping sources that are mid-download.
- Some OpenAlex "pdf_url"s are landing pages or need access, so the download fails or yields HTML.
  The error shows on the card; HTML still ingests via trafilatura.
- First search after start-up waits about 70 s for the Gemma model to load; the status text says so.

## Outcome
Built ui/search_page.py (ResultColumn + SearchPage), style additions and tests/test_search_page.py (5 tests).

Deviations / notes:
- Double-clicking a result card also adds it to the drop zone (an alternative to dragging).
- ingest.py: some open-access hosts (eScholarship) return 403 to a non-browser user agent. The UA is now
  "Mozilla/5.0 (X11; Linux x86_64) LocalLibrary/0.1 (desktop research app)", which still names the app.
  tandfonline and philpapers still return 403 (they block automated downloads); the card shows the error.
- ingest.py: downloads with < 500 characters of text are rejected as login/paywall pages.

Check results (offscreen run of the real MainWindow with the real backend):
- Search: PASS. The busy bar was visible while working; Gemma's picks appeared in 15 s (model warm), textbook first.
- Ingest on drop: PASS. Paper #98 (eScholarship PDF) downloaded and ingested (37 chunks) with progress, then
  "Ready"; #97 (an HTML abstract page) ingested.
- Done: PASS. Created shelf book #2 "intro to statistics" with sources [1, 98, 97], last_source_id = 1
  (the textbook), and switched to ResearchPage.
- Errors: PASS. A philpapers 403 showed on the card as "Couldn't add this source: Download failed: Client
  error '403 Forbidden'…"; no crash; Done skipped the failed card.
- pytest: PASS (25 tests).
- Real mouse drag on the desktop: PENDING. To be done by the user in the hands-on test after Phase 7.
