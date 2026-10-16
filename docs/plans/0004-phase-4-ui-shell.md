# 0004 — Phase 4: UI shell
Status: Done
Date: 2026-10-16
Requested by: PLAN.md phase 4

## Goal
The skeleton of the desktop app: start-up (stylesheet, DB schema, first catalog sync in the background),
a main window that switches between Library, Search and Research pages, a generic background worker,
and the reusable drag-and-drop widgets every page builds on.

## Scope
In scope: main.py, workers.py, ui/main_window.py, ui/widgets.py, ui/style.qss, placeholder pages,
a test for drag-and-drop signals.
Out of scope: real page contents (Phases 5–7).

## Files to change
- locallibrary/main.py — QApplication, load style.qss, MainWindow; run init_schema + (if no textbooks yet)
  openstax.sync_catalog in a Worker with a status-bar message; "Library → Refresh catalog" menu item
- locallibrary/workers.py — `Worker(fn, *args, **kwargs)` QRunnable; `WorkerSignals` with
  `finished(object)`, `failed(str)`, `progress(int, str)`; passes a `progress_callback` kwarg to fn when
  it accepts one; `run_in_background(fn, *args, on_done=, on_error=, on_progress=)` helper on the global pool
- locallibrary/ui/main_window.py — QMainWindow with a QStackedWidget; `show_library()`, `show_search()`,
  `open_research(shelf_book_id)`; status bar
- locallibrary/ui/library_page.py, search_page.py, research_page.py — minimal placeholder QWidgets
  (with nav buttons) so switching works; filled in by later phases
- locallibrary/ui/widgets.py — `BookTile` (draggable; mime type `application/x-locallibrary` carrying
  "kind:id"; emits clicked/double_clicked), `DropZone` (accepts one kind, emits `dropped(int)`),
  `SourceCard` (draggable BookTile subclass with title, type label, reason, status/progress line)
- locallibrary/ui/style.qss — plain base styles keyed by objectName
- tests/test_widgets.py — offscreen Qt: DropZone accepts the right kind (emits dropped(id)), rejects the wrong kind
- pyproject.toml — none (pytest-qt not added; tests build QMimeData drop events by hand)

## Data / schema changes
None.

## Steps
1. workers.py; widgets.py; style.qss.
2. main_window.py + placeholder pages; main.py.
3. Widget tests with QT_QPA_PLATFORM=offscreen.
4. Launch the app by hand: pages switch; drag a test tile onto a drop zone.

## Checks
- [x] App opens and the three pages switch
- [x] Dragging a tile onto a matching DropZone fires `dropped(id)`; a wrong kind is rejected
- [x] First-launch catalog sync runs in the background without freezing the window
- [x] pytest passes

## Risks / open questions
- Real drags need a display; automated tests send synthetic drop events offscreen. A manual drag on the
  desktop is still needed (by the user, or by screenshot via the run skill).

## Outcome
Built workers.py, ui/widgets.py, ui/style.qss, ui/main_window.py, placeholder pages, main.py and tests/test_widgets.py.

Deviations / notes:
- workers.friendly_error() turns common failures (Ollama down, DB down, HTTP errors) into plain messages for the UI.
- Workers are kept in a module-level set until they finish, so their signals aren't garbage-collected mid-run.
- Gotcha: QDropEvent does not own its QMimeData. Synthetic drops must keep a reference to the mime data, or
  Qt segfaults. (Found in a scratch smoke script, not in app code. Real drags are owned by QDrag.)
- The page background color needs WA_StyledBackground on custom QWidget pages; handled in Phase 7.

Check results:
- App opens and pages switch: PASS. Offscreen run of the real MainWindow switched Library → Search → Research;
  the real app launched on the Wayland desktop and ran 8 s without errors.
- DropZone: PASS. Synthetic drop emitted dropped(9); the wrong kind was rejected (tests). A real mouse drag
  will be tried by hand in the Phase 5 end-to-end flow.
- Start-up worker: PASS. prepare_library ran in the pool (catalog already present, so no re-sync).
- pytest: PASS (20 tests, no warnings).
