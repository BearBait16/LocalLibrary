# 0012 — Sources as books (Search and Research pages)
Status: Done
Date: 2026-10-16
Requested by: "can choosing relative sources and other chosen sources, can they be books too?" (chose: spines on a
shelf; results, picks and the Research page)

## Goal
Show sources as book spines standing on shelves, like the Library, everywhere they can be picked or chosen: the Search
page results and picks, and the Research page source strip and Similar Sources panel.

## Scope
In scope:
- `SourceSpine`: a spine for a source. Color comes from the source id (same 8-color palette as shelf books), design from
  its type (textbook = gold bands, paper = title label, web article = ribbed), plus a colored type cap at the bottom
  (TEXTBOOK / PAPER / WEB). Tooltip: title, type, origin, reason or description, and the cover image when cached.
- `SourceShelf`: wrapping rows of spines with a shelf board under each row; sits in a scroll area.
- Search page: both result columns become shelves; clicking a spine shows its title and "why" (Gemma's reason) in a
  line under the shelf; double-click or drag still adds it. The "Drag here!" box holds a "Your picks" shelf. Pick
  spines show download progress as a thin bar at the bottom, a red outline if the download failed (the error also
  shows under the search box), and a small ✕ to remove.
- Research page: the source strip and Similar Sources panel become shelves (2 spines per row). The open source's spine is
  highlighted. Covers still show in the Now-reading bar.
Out of scope: the falling animation (plan 0013), changing a source's spine look by hand, the Library page.

## Files to change
- locallibrary/ui/widgets.py — `SourceSpine(BookSpine)`, `SourceShelf`, pure `shelf_slots(count, width)`; remove the
  now-unused `SourceCard` and `SourceTile`
- locallibrary/looks.py — `source_look(source) -> (color, design)`
- locallibrary/ui/search_page.py — ResultColumn holds a SourceShelf + details line; picks shelf in the drop zone
- locallibrary/ui/research_page.py — strip and Similar panel use SourceShelf/SourceSpine
- locallibrary/ui/style.qss — type cap, shelf board, spine progress / error / remove button; drop old card/tile rules
- tests/test_looks.py, tests/test_widgets.py, tests/test_search_page.py — source_look, shelf_slots, spine status
- README.md — Search/Research usage wording; PLAN.md left as history

## Data / schema changes
None.

## Steps
1. `source_look` + `shelf_slots` with tests.
2. `SourceSpine` and `SourceShelf` + QSS.
3. Search page columns and picks shelf; keep the existing state machine (ready / downloading / failed).
4. Research page strip and Similar panel.
5. Remove SourceCard / SourceTile; pytest; offscreen screenshots of both pages.

## Checks
- [x] Search results show as spines on shelves; click shows the reason; double-click and drag add to picks
- [x] Picks show progress while downloading, red outline + message on failure, ✕ removes; Done still works
- [x] Research strip and Similar panel show spines; clicking opens the source; the open one is highlighted;
      dragging a similar spine onto the page still adds it
- [x] Spine color/design is stable for a source (same look every time)
- [x] pytest passes; the app starts

## Risks / open questions
- The reason text is no longer always visible; it moves to the click-to-show line and the tooltip.
- Spines are 76 px wide, so the Research strip fits 2 per row and long titles are shortened (full title in tooltip).

## Outcome
Built `SourceSpine` (a `BookSpine` that drags as a source, with a type cap, progress bar, error outline, ✕ button and a
rich tooltip with cover / reason), `SourceShelf` (manual layout: wrapping rows of spines over `SourceShelfBoard`
frames) and `shelf_slots`, plus `looks.source_look` (color = id % 8, design by type). The Search page columns, the
picks box, the Research strip and the Similar panel all use them. `SourceCard` and `SourceTile` were removed, along
with their QSS.

Deviations: the cover moved from the strip tile into the spine's hover tooltip (the Now-reading bar still shows it).
A failed download also shows its message in the error line under the search box, since the spine has no room for text.

Check results:
- Search results / picks: PASS (offscreen screenshot with real sources 1, 98, 40, 33, 97, …: 7 spines on one shelf,
  clicked spine highlighted with its reason shown underneath; two picks with ✕). Double-click and drop use the
  same signals as before; the drag MIME is checked in tests/test_widgets.py.
- Picks status: PASS (tests: progress shows/hides, error property set, message shown, remove takes it off the shelf;
  existing Done-button tests unchanged and passing).
- Research: PASS (offscreen screenshot of shelf book #2: 5 spines, 2 per shelf, open source highlighted; Similar panel
  shows 8 spines). A real mouse drag hasn't been tried by hand yet.
- Stable look: PASS (tests/test_looks.py).
- pytest: PASS (54 tests). App starts (MainWindow built and shown offscreen).
