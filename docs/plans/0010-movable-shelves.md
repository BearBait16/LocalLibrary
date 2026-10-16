# 0010 — Four shelves with drag-to-move books
Status: Done
Date: 2026-10-16
Requested by: "I want multiple shelves to move them around on" — fixed set of 4 shelves; no wrap; once all
4 rows are full, no more books can be added ("something that will change later")

## Goal
Turn the library into a bookcase of 4 fixed shelves. Each book has a shelf and a place on it; the user drags
books to reorder them on a shelf or move them to another shelf, and the arrangement is saved. Each shelf holds a
fixed number of books with no wrapping or scrolling. When every shelf is full, new research can't be saved until
a book is deleted.

## Scope
In scope: shelf placement storage, moving/reordering, capacity limits, the full-library state.
Out of scope: adding/naming shelves, scrolling shelves (the capacity is one constant, so it can change later).

## Files to change
- locallibrary/config.py — `SHELF_COUNT = 4`, `SHELF_CAPACITY = 10` (the one place to change later)
- locallibrary/db.py — `shelf_books.shelf int`, `shelf_books.shelf_position int`; `create_shelf_book` places the book
  at the end of the first shelf with room and raises `LibraryFull` when there's none; `move_shelf_book(id, shelf, index)`
  (reorder or move; refuses a full target shelf; keeps positions 0..n-1 with no gaps); delete closes the gap; backfill
  for existing books; `list_shelf_books` ordered by shelf, position; `library_is_full()`
- locallibrary/models.py — `ShelfBook.shelf`, `ShelfBook.shelf_position`
- locallibrary/ui/library_page.py — 4 `ShelfRow`s always shown (empty ones too); each accepts dropped books, shows an
  insertion marker where the book will land, and turns "full" (red) when it can't take a book from another shelf.
  "New research" is disabled with a message when the library is full
- locallibrary/ui/widgets.py — `ShelfRow` (drop target computing the insertion index from the drop position; emits
  `book_dropped(book_id, index)`)
- locallibrary/ui/search_page.py — Done shows "Your bookcase is full…" if `LibraryFull` is raised
- locallibrary/ui/style.qss — shelf row, insertion marker, full-shelf states; spine size so 10 fit on a row
- tests/test_db.py, tests/test_shelf_row.py — placement, reorder, move, full shelf, full library, gap closing;
  insertion-index math

## Data / schema changes
`ALTER TABLE shelf_books ADD COLUMN IF NOT EXISTS shelf integer`, `ADD COLUMN IF NOT EXISTS shelf_position integer`.
Existing books are placed in creation order (filling shelf 1 first).

## Steps
1. Config constants; db placement/move/full + tests. 2. ShelfRow + tests. 3. Library page bookcase.
4. Search page full message. 5. Scripted check (move, reorder, restart, full library) + screenshot.

## Checks
- [x] Books can be reordered on a shelf and moved to another shelf; the layout survives a restart
- [x] A full shelf rejects books from other shelves; reordering within a full shelf still works
- [x] With all 4 shelves full: New research is disabled with a message; Done refuses with a message
- [x] Deleting a book frees its spot
- [x] pytest passes

## Risks / open questions
- Capacity of 10 per shelf (40 books total) was chosen so 10 spines fit across the default window without
  scrolling. If the window is made much narrower the spines get squeezed; the minimum window width is set to match.
- Real mouse drags still need the user's hands-on test.

## Outcome
Built: SHELF_COUNT/SHELF_CAPACITY in config.py; shelf/shelf_position columns, placement, move_shelf_book,
ShelfFull/LibraryFull, library_is_full, gap closing and backfill in db.py; ShelfRow + insertion_index in widgets.py
(the gold drop marker is positioned by hand, outside the layout, so spines don't shift mid-drag); a 4-shelf bookcase
on the Library page with a full-bookcase notice; the LibraryFull message on the Search page; tests/test_shelf_row.py
and 4 shelf tests in tests/test_db.py; README + AGENTS.md updated.

Bug found and fixed during checks:
- The Library page first judged "full" by total book count while create_shelf_book used free room per shelf. In a
  shrunken test bookcase they disagreed, and Done saved a book although the page said "full". The page now uses
  db.library_is_full(), the same rule as create_shelf_book. The stray test book (#8 "x") was deleted.

Layout notes:
- Rows have a fixed height (176 px) so empty shelves keep their size, and a minimum width of 10 spine slots. The shelf
  area passes that minimum up to the window (min width ≈ 1112 px), so a full shelf is never clipped. All 4 shelves fit
  in the default 1280 × 820 window without scrolling.

Check results:
- Move/reorder + restart: PASS. Book 7 dropped on shelf 2 → [[1, 2], [7]]; book 2 dropped at the front of shelf 1 →
  [[2, 1], [7]]; same layout after a restart. The user's books were then restored to [[1, 2, 7]].
- Full shelf: PASS. Rejects another shelf's book (red state, drop ignored) but allows reordering (tests/test_shelf_row.py;
  ShelfFull in tests/test_db.py).
- Full bookcase (simulated in memory, 2 × 1): PASS. New research is disabled with "Your bookcase is full…"; Done on the
  Search page shows "Your bookcase is full. Delete a book…" and saves nothing.
- Delete frees a spot: PASS (tests/test_db.py).
- 10 spines fit on a row at the minimum width with no overlap: PASS.
- App starts on the desktop: PASS (8 s launch, no errors).
- pytest: PASS (48 tests).
- Real mouse drags: PENDING. Still part of the user's hands-on test.
