# 0013 — Search results fall in with physics
Status: Done
Date: 2026-10-16
Requested by: "Could we add physics to the books? Make it so the sources fall from the top of the screen when you
search the sources" (chose: fall, bounce, settle; no physics library)

## Goal
When search results arrive, each result spine drops from the top of the window one after another, speeds up under
gravity, bounces a little on its shelf and settles in place.

## Scope
In scope: the Search page result shelves (local and Gemini columns; Gemini results fall when they arrive).
Out of scope: collisions between books, throwing books, animating picks or the Research/Library pages, new dependencies.

## Files to change
- locallibrary/ui/falling.py (new) — `Body` dataclass and `step(body, dt)` (gravity, bounce with damping, settle);
  `FallLayer(QWidget)`: a mouse-transparent overlay that paints each falling spine's picture and shows the real spine
  when it lands
- locallibrary/ui/search_page.py — create the overlay; drop new result spines through it; finish instantly on a new
  search, reset or resize
- tests/test_falling.py — the body speeds up, bounces lower each time, settles exactly on its shelf; the layer shows
  every spine when finished
- AGENTS.md — layout: ui/falling.py

## Data / schema changes
None.

## Steps
1. falling.py physics + tests.
2. FallLayer overlay: 60 fps QTimer, staggered start (about 90 ms apart), targets read from each spine's live position
   every frame (so scrolling during a fall is fine).
3. Hook into SearchPage._show_recommendation / _show_web.
4. Try it offscreen (frame grabs) and by hand.

## Checks
- [x] Results fall from the top of the window, bounce and settle in their shelf slots
- [x] A spine can be clicked / dragged once it has landed; nothing is lost if a new search starts mid-fall
- [x] Spines that are scrolled out of view just appear (no animation needed)
- [x] The UI thread stays responsive (animation is a light timer, no blocking)
- [x] pytest passes; the app starts

## Risks / open questions
- Depends on plan 0012 (spines on shelves).
- While falling, a spine's picture passes over the search box and headings; that's intended ("top of the screen").

## Outcome
Built `locallibrary/ui/falling.py`: `Body` + `step()` (gravity 3200 px/s², keeps 35% of its speed per bounce, rests
below 90 px/s, frames capped at 50 ms so a busy moment can't push a book through its shelf) and `FallLayer`, a
mouse-transparent overlay that hides each spine, paints its picture falling from the top of the page (90 ms apart)
and shows the real spine when it lands. SearchPage drops the local results when Gemma answers and the Gemini results
when they arrive; `start_search` and `reset` call `finish()` first so no spine is left hidden.

Deviation: the plan said to finish instantly on resize. Instead the landing spot is re-read from each spine every
frame, so a resize or scroll mid-fall just moves the landing spot. The overlay is resized with the page.

Check results:
- Fall/bounce/settle: PASS. Contact sheet of 12 offscreen frames 100 ms apart (7 real sources): books enter at the
  top, pass over the heading and search box one after another, and bounce onto the shelf. tests/test_falling.py:
  speeds up, each bounce is lower, never sinks below the shelf, ends exactly on it.
- Clickable after landing / new search mid-fall: PASS (spines are the real widgets, hidden only while falling;
  `finish()` shows all of them; test covers it).
- Off-view spines: PASS (test: a spine outside the column's viewport isn't animated and stays visible).
- Responsive: PASS (16 ms QTimer; each frame is a few float updates and pixmap draws).
- pytest: PASS (59 tests). App starts (`python -m locallibrary.main` ran offscreen until the timeout with no errors).
- Not yet tried on a real screen by hand.
