from locallibrary.models import RESEARCH_PAPER, TEXTBOOK, Source
from locallibrary.rag import cited_numbers
from locallibrary.recommend import fallback, validate_pick

BOOKS = [Source(f"Book {i}", TEXTBOOK, "openstax", f"b{i}", id=i) for i in (1, 2)]
PAPERS = [Source(f"Paper {i}", RESEARCH_PAPER, "openalex", f"p{i}", id=i) for i in range(10, 18)]


def test_valid_pick():
    pick = {"textbook_id": 2, "textbook_reason": "best", "papers": [
        {"id": 12, "reason": "a"}, {"id": 11, "reason": "b"}, {"id": 15, "reason": "c"}]}
    rec = validate_pick(pick, BOOKS, PAPERS)
    assert rec.textbook.id == 2
    assert [p.id for p in rec.papers] == [12, 11, 15]
    assert rec.reasons[2] == "best" and rec.reasons[11] == "b"


def test_unknown_ids_are_dropped_and_too_few_rejects():
    pick = {"textbook_id": 2, "textbook_reason": "", "papers": [
        {"id": 12, "reason": ""}, {"id": 999, "reason": ""}, {"id": "x", "reason": ""}, {"id": 12, "reason": ""}]}
    assert validate_pick(pick, BOOKS, PAPERS) is None


def test_bad_textbook_rejects():
    pick = {"textbook_id": 99, "papers": [{"id": i, "reason": ""} for i in (10, 11, 12)]}
    assert validate_pick(pick, BOOKS, PAPERS) is None


def test_caps_at_six_papers():
    pick = {"textbook_id": 1, "papers": [{"id": p.id, "reason": ""} for p in PAPERS]}
    assert len(validate_pick(pick, BOOKS, PAPERS).papers) == 6


def test_fallback_uses_vector_order():
    rec = fallback(BOOKS, PAPERS)
    assert rec.textbook.id == 1 and [p.id for p in rec.papers] == [10, 11, 12, 13, 14]
    assert rec.used_fallback


def test_cited_numbers():
    assert cited_numbers("See [2] and [1, 3]; also [2] and [9].", 6) == [2, 1, 3]
    assert cited_numbers("no citations", 6) == []
