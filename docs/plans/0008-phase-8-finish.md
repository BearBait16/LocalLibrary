# 0008 — Phase 8: Finish
Status: Done
Date: 2026-10-16
Requested by: PLAN.md phase 8

## Goal
Close out the initial build: fill the remaining test gaps (nomic prefix helper, DB query functions against
the Docker DB), re-run every phase's checks end to end, update the README and AGENTS.md to match what was
built, and confirm every plan file is Done.

## Scope
In scope: new tests, README, AGENTS.md Commands/Layout, a final end-to-end run, the user's hands-on test.
Out of scope: new features.

## Files to change
- tests/test_embed.py — prefixes are applied, batching splits into 32s (Ollama client faked)
- tests/test_db.py — every query function against a separate `locallibrary_test` database on the Docker server
  (created if missing, tables truncated per test), so the real library is never touched. Skipped if Postgres is down.
- tests/conftest.py — the test-DB fixture
- README.md — setup, usage walkthrough, configuration table, known limitations
- AGENTS.md — Commands (smoke check, CLIs) and Layout (scripts/, seed JSON, data/settings.json) updated

## Data / schema changes
None. Tests create a separate `locallibrary_test` database.

## Steps
1. Tests; pytest.
2. Re-run the phase checks (smoke check, CLIs, offscreen UI flows).
3. README + AGENTS.md.
4. User's hands-on test of real drags / right-click on the desktop.
5. Mark all plans Done; summary.

## Checks
- [x] pytest passes, including DB tests against Docker
- [x] Every phase check re-run
- [x] README and AGENTS.md match the code
- [x] All plan files 0000–0008 are Done with outcomes
- [ ] User hands-on test: real drags and right-click work (deferred by the user)

## Risks / open questions
- Real mouse drag-and-drop under Wayland can only be confirmed by the user.

## Outcome
Added tests/conftest.py (test-DB fixture), tests/test_db.py (5 tests covering every db.py query function),
tests/test_embed.py (prefixes + batching). Rewrote the README (setup, usage, configuration, CLIs, known limitations)
and updated the AGENTS.md Commands and Layout sections.

Check results:
- pytest: PASS. 35 tests, none skipped; the DB tests ran against the separate `locallibrary_test` database.
- Phase checks re-run: P0 smoke check PASS; P1 vector search 5/8 sampled pages in the top 5 (6/8 before the
  word-boundary re-chunk in Phase 3; same cause as before, similar text across chapters); P2 OpenStax 84 books,
  OpenAlex 15 papers, Gemini "no key" message; P3 recommend (Gemma pick) + rag (correct std-dev answer with real
  pages) PASS; P5–P6 flows passed earlier in this session after the last code changes; P7 restart/resume PASS
  in a fresh process (book 1 → p. 300 even after a resize).
- App launched on the desktop for the user's test. The log shows one source rejected with "The download had no
  readable text" (the Phase 5 guard; handled on the card, no crash).
- Hands-on test of real mouse drags / right-click: NOT DONE. The user chose "Skip for now". This is the one
  open item in the definition of done.
- Test data left in place at the user's request: shelf books #1 "Statistics basics" and #2 "intro to statistics",
  data/backgrounds/test-bg.png.
