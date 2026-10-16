# 0007 — Phase 7: Library page
Status: Done
Date: 2026-10-16
Requested by: PLAN.md phase 7

## Goal
The home screen: every saved research session shown as a book on a shelf over a background picture
the user can change. Drag a book onto "Open" (or double-click it) to resume it, right-click to
rename or delete it, and start new research from here.

## Scope
In scope: ui/library_page.py, settings helpers, style additions, tests for settings.
Out of scope: rotated spine titles (optional in PLAN.md; skipped to keep it simple).

## Files to change
- locallibrary/config.py — `load_settings()` / `save_settings(dict)` for `data/settings.json` (holds `background`)
- locallibrary/ui/library_page.py
  - full-page background: the chosen image painted scaled-to-cover in paintEvent; plain stylesheet background if none
    or the file is missing (WA_StyledBackground set so the QSS background applies)
  - "Change background…" → QFileDialog (images) → copy into data/backgrounds/ → save setting → repaint;
    "Clear background" when one is set
  - shelf: BookTiles (kind shelf_book, objectName ShelfSpine) in rows of 8 inside a scroll area, each row
    on a shelf board; empty-state message
  - "Open" DropZone (kind shelf_book) → window.open_research(id); double-click a book does the same
  - "New research" → window.show_search()
  - right-click a book → Rename… (QInputDialog) / Delete… (QMessageBox confirm; deletes the shelf book only,
    downloaded files stay)
  - refresh() reloads from db.list_shelf_books()
- locallibrary/ui/style.qss — library page objectNames
- tests/test_settings.py — settings round trip and a missing/corrupt file → {}
- locallibrary/ui/research_page.py, ui/main_window.py — (added during this phase) fix for the PDF resume bug found by the restart check; see Outcome

## Data / schema changes
None in Postgres. New local file `data/settings.json` (already in .gitignore).

## Steps
1. Settings helpers + tests.
2. Library page layout, background painting, shelf, Open zone, context menu.
3. Scripted check across two app processes (restart), plus screenshot.

## Checks
- [x] Two shelf books show on the shelf; after restarting the app both are still there and each resumes on its own saved source/page
- [x] Dropping a book on Open (and double-clicking) opens the Research page
- [x] Change background copies the image into data/backgrounds/ and it persists across restart
- [x] Rename and delete work; delete leaves the downloaded files in place
- [x] pytest passes

## Risks / open questions
- Settings live in a JSON file rather than a DB table (PLAN.md allows either). This keeps the schema unchanged.

## Outcome
Built ui/library_page.py, config.load_settings/save_settings, style additions and tests/test_settings.py.

Bug found and fixed (in the Research page, caught by this phase's restart check):
- In a freshly started app, book 1 saved at page 300 reopened at page 189 and saved 189 over 300. The first
  QPdfView.jump() happened before the view had its real size; FitToWidth then re-zoomed while keeping the pixel
  offset, so the navigator reported (and the page saved) a different page. Window resizes caused the same drift
  (300 → 484).
- Fix: open_research() now shows the page before loading. ResearchPage ignores page signals for 300 ms after a PDF
  opens or the view resizes (`restoring_page`), then jumps to the reader's page again. A user jump during that
  window takes priority.
- Phase 6's flow was re-run after the fix and still passes.

Other notes:
- QSS: a bottom-only border on a QFrame needs `border: none;` first, or Qt draws nothing (styling only).
- The settings file is data/settings.json (gitignored).

Check results (scripted, two separate app processes):
- Two books on the shelf; after restart both are there, and each resumes on its own source/page: PASS
  (book 1 → source 1 p. 300; book 2 → source 98 p. 3), repeated in two fresh processes. After a resize: still p. 300.
- Drop on Open → Research page (book 2): PASS. Double-click → Research page (book 1): PASS.
- Change background: PASS. Copied to data/backgrounds/test-bg.png, saved in settings.json, and loaded after restart.
- Rename: PASS ("Statistics basics"). Delete (confirm auto-accepted in the script): PASS. The book was removed;
  the downloaded files and sources' downloaded flags were untouched.
- pytest: PASS (29 tests).
- Real mouse drags and the right-click menu on the desktop: PENDING, part of the user's hands-on test.
