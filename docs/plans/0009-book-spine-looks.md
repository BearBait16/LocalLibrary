# 0009 — Book spine colors and edge designs
Status: Done
Date: 2026-10-16
Requested by: "I want each book to be a different color, maybe have different designs on the edge"

## Goal
Make every book on the shelf look different: each shelf book gets a spine color and an edge design.
New books are given one automatically, chosen so the books next to each other don't match, and the user can
change it with right-click → "Change look…". The look is saved per book.

## Scope
In scope: per-book color + design (stored), automatic assignment, the "Change look…" dialog, spine rendering.
Out of scope: shelves and moving books (plan 0010), custom colors outside the palette, rotated titles.

## Files to change
- locallibrary/db.py — `shelf_books.spine_color int`, `shelf_books.spine_design text` (added with
  `ALTER TABLE … ADD COLUMN IF NOT EXISTS`); `create_shelf_book` assigns a look; `set_spine_look(id, color, design)`;
  existing books without a look are backfilled in `init_schema`
- locallibrary/models.py — `ShelfBook.spine_color`, `ShelfBook.spine_design`
- locallibrary/looks.py (new) — the palette's names (`SPINE_COLORS`, 8 entries) and `SPINE_DESIGNS`
  (`bands`, `label`, `two_tone`, `ribbed`), plus `pick_look(used_counts, avoid)`: the least-used color and design,
  never equal to `avoid` (the neighbor's look). Pure functions, no Qt and no hex values.
- locallibrary/ui/widgets.py — `BookSpine(BookTile)`: sets the `spineColor` / `spineDesign` properties and builds
  the design from child frames (`SpineBand`, `SpineLabel`, `SpineTone`, `SpineRib`) around the title
- locallibrary/ui/style.qss — 8 `QFrame#ShelfSpine[spineColor="N"]` colors; decoration styles use translucent
  gold/dark overlays so every design works on every color (all hex values stay in the stylesheet)
- locallibrary/ui/library_page.py — use BookSpine; right-click "Change look…" opens `SpineLookDialog`
- locallibrary/ui/look_dialog.py (new) — dialog with a row of sample spines for colors and one for designs,
  rendered by the same BookSpine + QSS, plus a live preview of the chosen look
- tests/test_looks.py, tests/test_db.py — pick_look rules; look assigned on create, backfill, set_spine_look

## Data / schema changes
`ALTER TABLE shelf_books ADD COLUMN IF NOT EXISTS spine_color integer`,
`ADD COLUMN IF NOT EXISTS spine_design text`. Existing rows are backfilled in creation order.

## Steps
1. looks.py + tests. 2. db columns, assignment, backfill, set_spine_look + tests.
3. BookSpine + QSS. 4. Library page + Change look dialog. 5. Screenshot check.

## Checks
- [x] Existing books get a look after the upgrade; each new book's look differs from its left neighbor's
- [x] All 4 designs render on all 8 colors (screenshot of the dialog)
- [x] Change look… saves and survives a restart
- [x] pytest passes

## Risks / open questions
- The automatic pick is decided at creation; after books are moved (0010) neighbors may happen to match. The user can change any book's look.

## Outcome
Built looks.py (palette names, designs, pick_look), the db columns + backfill + set_spine_look, BookSpine in
widgets.py, ui/look_dialog.py (SpineLookDialog), the "Change look…" menu item, and QSS for 8 colors × 4 designs.

Deviations / notes:
- Qt stylesheets have no sibling selector, so two-tone parts carry an `edge` property (top/bottom) instead.
- Spine titles are fitted to each design's free space (`fit_text`): words are dropped from the end with "…",
  and a single word wider than the spine is shortened on its own. The full title is in the tooltip. Added because
  the user's book "Data analyzation and how I can make graphs" overflowed the two-tone design.
- Styling only: on the Library page, the heading sits on a light panel so it reads on dark backgrounds (the user's
  painting background), and the "selected" outline in the dialog is thicker.
- Spines are now a fixed 76 × 160 px (previously 70–90 × 220) to prepare for 4 shelves (plan 0010).

Check results:
- Backfill: PASS. Existing books 1, 2, 7 got (Oxblood, bands), (Navy, label), (Forest, two_tone).
- New books differ from their left neighbor: PASS (tests/test_looks.py: 20 books in a row; tests/test_db.py).
- All designs on all colors: PASS (dialog screenshots for each design across the 8 colors).
- Change look… persists: PASS. Book 1 set to (Chocolate, ribbed) in one process and read back after a restart,
  then restored to its original look.
- pytest: PASS (41 tests).
