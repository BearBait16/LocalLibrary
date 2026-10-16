from locallibrary.config import EMBED_DIM
from locallibrary.models import RESEARCH_PAPER, TEXTBOOK, Source


def vec(i: int) -> list[float]:
    v = [0.0] * EMBED_DIM
    v[i] = 1.0
    return v


def add(db, title, kind=TEXTBOOK, axis=0, url=None):
    return db.upsert_source(Source(title, kind, "openstax", url or f"https://x/{title}", "desc"), vec(axis))


def test_upsert_get_and_conflict_keeps_download_state(test_db):
    db = test_db
    s = add(db, "Stats")
    db.mark_downloaded(s.id, "/tmp/stats.pdf")
    again = db.upsert_source(Source("Stats 2e", TEXTBOOK, "openstax", s.url, "new desc"))
    assert again.id == s.id and again.title == "Stats 2e" and again.downloaded
    assert db.get_source(s.id).local_path == "/tmp/stats.pdf"
    assert db.get_source_by_url(s.url).id == s.id
    assert db.get_summary_embedding(s.id)[0] == 1.0  # kept when the upsert had no embedding
    assert db.count_sources() == 1 and db.count_sources(RESEARCH_PAPER) == 0


def test_get_sources_keeps_order(test_db):
    a, b, c = (add(test_db, n) for n in "abc")
    assert [s.id for s in test_db.get_sources([c.id, a.id, b.id])] == [c.id, a.id, b.id]


def test_search_sources_type_filter_and_exclude(test_db):
    db = test_db
    near = add(db, "near", axis=0)
    add(db, "far", axis=5)
    paper = add(db, "paper", kind=RESEARCH_PAPER, axis=0)
    results = db.search_sources(vec(0), TEXTBOOK, limit=5)
    assert [s.id for s, _ in results][0] == near.id
    assert paper.id not in [s.id for s, _ in results]
    assert near.id not in [s.id for s, _ in db.search_sources(vec(0), exclude_ids=[near.id])]


def test_chunks_replace_and_search(test_db):
    db = test_db
    a, b = add(db, "a"), add(db, "b")
    db.replace_chunks(a.id, [(1, "one", vec(1)), (2, "two", vec(2))])
    db.replace_chunks(a.id, [(3, "three", vec(3))])  # replaces, never duplicates
    db.replace_chunks(b.id, [(7, "seven", vec(3))])
    assert db.count_chunks(a.id) == 1
    hits = db.search_chunks(vec(3), [a.id])
    assert [(h.source_id, h.page, h.text) for h in hits] == [(a.id, 3, "three")]
    assert {h.source_id for h in db.search_chunks(vec(3))} == {a.id, b.id}


def test_shelf_book_crud(test_db):
    db = test_db
    a, b, c = (add(test_db, n) for n in "abc")
    book = db.create_shelf_book("Topic", "topic", [b.id, a.id], b.id)
    assert db.get_shelf_book(book.id).source_ids == [b.id, a.id]
    db.add_source_to_shelf_book(book.id, c.id)
    db.add_source_to_shelf_book(book.id, c.id)  # no duplicate
    db.save_position(book.id, c.id, 42)
    db.rename_shelf_book(book.id, "Renamed")
    got = db.get_shelf_book(book.id)
    assert got.source_ids == [b.id, a.id, c.id] and (got.last_source_id, got.last_page) == (c.id, 42)
    assert [x.title for x in db.list_shelf_books()] == ["Renamed"]
    db.delete_shelf_book(book.id)
    assert db.get_shelf_book(book.id) is None and db.get_source(a.id) is not None


def test_spine_looks_assigned_backfilled_and_changed(test_db):
    db = test_db
    a = db.create_shelf_book("A", "a", [], None)
    b = db.create_shelf_book("B", "b", [], None)
    assert (a.spine_color, a.spine_design) != (b.spine_color, b.spine_design)
    assert a.spine_color != b.spine_color and a.spine_design != b.spine_design
    with db.connect() as conn:  # simulate a book saved before looks existed
        conn.execute("UPDATE shelf_books SET spine_color = NULL, spine_design = NULL WHERE id = %s", (b.id,))
    db.init_schema()
    b2 = db.get_shelf_book(b.id)
    assert b2.spine_design is not None and b2.spine_color != a.spine_color
    db.set_spine_look(a.id, 5, "ribbed")
    got = db.get_shelf_book(a.id)
    assert (got.spine_color, got.spine_design) == (5, "ribbed")


import pytest


@pytest.fixture
def small_case(test_db, monkeypatch):
    monkeypatch.setattr(test_db, "SHELF_COUNT", 2)
    monkeypatch.setattr(test_db, "SHELF_CAPACITY", 3)
    return test_db


def layout(db):
    shelves = {}
    for book in db.list_shelf_books():
        shelves.setdefault(book.shelf, []).append(book.title)
    return shelves


def test_books_fill_shelves_in_order_and_library_fills_up(small_case):
    db = small_case
    for title in "abcdef":
        db.create_shelf_book(title, title, [], None)
    assert layout(db) == {0: ["a", "b", "c"], 1: ["d", "e", "f"]}
    assert db.library_is_full()
    with pytest.raises(db.LibraryFull):
        db.create_shelf_book("g", "g", [], None)


def test_reorder_within_shelf(small_case):
    db = small_case
    a, b, c = (db.create_shelf_book(t, t, [], None) for t in "abc")
    db.move_shelf_book(c.id, 0, 0)
    assert layout(db) == {0: ["c", "a", "b"]}
    db.move_shelf_book(c.id, 0, 99)  # past the end = last
    assert layout(db) == {0: ["a", "b", "c"]}


def test_move_between_shelves_closes_gap_and_respects_capacity(small_case):
    db = small_case
    books = {t: db.create_shelf_book(t, t, [], None) for t in "abcd"}
    db.move_shelf_book(books["b"].id, 1, 0)
    assert layout(db) == {0: ["a", "c"], 1: ["b", "d"]}
    assert [x.shelf_position for x in db.list_shelf_books() if x.shelf == 0] == [0, 1]
    db.move_shelf_book(books["a"].id, 1, 1)
    assert layout(db) == {0: ["c"], 1: ["b", "a", "d"]}
    with pytest.raises(db.ShelfFull):
        db.move_shelf_book(books["c"].id, 1, 0)
    db.move_shelf_book(books["d"].id, 1, 0)  # reordering a full shelf still works
    assert layout(db) == {0: ["c"], 1: ["d", "b", "a"]}


def test_delete_frees_spot_and_backfill_places_old_books(small_case):
    db = small_case
    books = [db.create_shelf_book(t, t, [], None) for t in "abcdef"]
    db.delete_shelf_book(books[1].id)
    assert layout(db)[0] == ["a", "c"] and not db.library_is_full()
    new = db.create_shelf_book("g", "g", [], None)
    assert (new.shelf, new.shelf_position) == (0, 2)
    with db.connect() as conn:  # books saved before shelves existed
        conn.execute("UPDATE shelf_books SET shelf = NULL, shelf_position = NULL")
    db.init_schema()
    assert sum(len(v) for v in layout(db).values()) == 6
