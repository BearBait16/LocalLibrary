# 0011 — Source covers and labels on the Research page
Status: Done
Date: 2026-10-16
Requested by: "I want the sources on the research page to have some kind of image or label of what source I'm looking at"

## Goal
Make it obvious which source is which, and which one is open. Source tiles on the Research page show a small cover
image (page 1 of the PDF) and a colored type badge, and a "Now reading" bar above the viewer shows the open source's
cover, title, type, origin and page.

## Scope
In scope: cover thumbnails (generated once, cached on disk), type badges, the "Now reading" bar, and the same tiles in
the Similar Sources panel (un-downloaded sources get a placeholder).
Out of scope: covers on the Search page cards or the Library spines; fetching cover art from the web.

## Files to change
- locallibrary/thumbnails.py (new) — `cover_path(source) -> Path | None`: renders page 1 of a downloaded PDF with
  PyMuPDF to `data/thumbnails/<id>.png` (about 240 px tall) once, then reuses it; None for web articles / not downloaded
- locallibrary/config.py — `Config.thumbnails_dir`
- locallibrary/ui/widgets.py — `SourceTile(BookTile)`: cover image (or a placeholder showing the type's initial),
  title, and a type badge (`sourceType` property for QSS colors); `set_cover(path)`; `ORIGIN_LABELS`
- locallibrary/ui/research_page.py — strip and Similar panel use SourceTile; covers load in a Worker (rendering is
  disk/CPU work); "Now reading" bar (`QFrame#NowReading`) updated on every source/page change
- locallibrary/ui/style.qss — tile, cover, placeholder, badge (one color per type) and Now-reading styles
- .gitignore — data/thumbnails/*
- AGENTS.md — layout: thumbnails.py, data/thumbnails/
- tests/test_thumbnails.py — renders + caches a cover for a generated PDF; None for HTML / not downloaded
- README.md — Research usage mentions covers and the Now-reading bar

## Data / schema changes
None in Postgres. New cache folder `data/thumbnails/` (safe to delete; covers are regenerated).

## Steps
1. thumbnails.py + tests. 2. SourceTile + QSS. 3. Research page strip, Similar panel, Now-reading bar.
4. Offscreen screenshot of shelf book #2 (textbooks, a paper, a web article).

## Checks
- [x] Each PDF source in the strip shows its cover; the web article shows a placeholder; every tile has a type badge
- [x] The Now-reading bar shows the open source's cover, title, type, origin and current page, and updates on switch/page change
- [x] Covers are cached (second open doesn't re-render)
- [x] The UI stays responsive while covers render (Worker)
- [x] pytest passes

## Risks / open questions
- Interpretation: "image or label" is taken as both: a cover picture and a text label.
- The strip gets taller per tile (about 130 px), so long books need scrolling in the strip.

## Outcome
Built thumbnails.py (PyMuPDF page-1 render, cached as data/thumbnails/<id>.png and re-rendered only if the PDF is newer),
CoverImage / type_badge / SourceTile in widgets.py, the Now-reading bar and background cover loading on the Research
page, the QSS for tiles, placeholders, badges and the bar, plus tests.

Notes:
- The strip and the Similar Sources panel both use SourceTile. Un-downloaded sources show a colored placeholder with the
  type's initial (T / P / W). Covers appear as soon as the background render finishes.
- Web articles say "Section n of m" in the bar; PDFs say "Page n of m".
- Source #1 (Introductory Statistics 2e) shows origin "Added by you" because it was first ingested with the CLI
  in Phase 1, before the OpenStax catalog sync (upserts don't change origin).

Check results (offscreen, real shelf book #2):
- Covers + badges: PASS. Covers for sources 1, 98, 40, 33 (PDFs); placeholder "P" for web/HTML source 97; badges on
  every tile, including the Similar panel.
- Now reading: PASS. Showed "Introduction to Business 2e · Textbook · OpenStax · Page 1 of 663"; after switching to 97,
  "Research paper · OpenAlex · Section 1 of 1" (placeholder cover); after open_source(1, 40), "Page 40 of 847".
- Cached: PASS (tests/test_thumbnails.py checks the file isn't rewritten; 4 PNGs in data/thumbnails/).
- Responsive: PASS. open_research returned in 0.12 s while covers rendered in a Worker.
- pytest: PASS (50 tests).
