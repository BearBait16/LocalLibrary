from locallibrary.ingest import chunk


def words(n: int, tag: str = "w") -> str:
    return " ".join(f"{tag}{i}" for i in range(n))


def test_short_page_is_one_chunk():
    assert chunk([(1, "hello   world\n\nagain")]) == [(1, "hello world again")]


def test_chunks_respect_size_and_page_tags():
    pages = [(1, words(600, "a")), (2, words(600, "b"))]
    chunks = chunk(pages)
    assert all(len(text) <= 1500 for _, text in chunks)
    assert [p for p, _ in chunks] == sorted(p for p, _ in chunks)
    assert {p for p, _ in chunks} == {1, 2}


def test_never_crosses_page_boundary():
    for page, text in chunk([(1, words(600, "a")), (2, words(600, "b"))]):
        prefix = "a" if page == 1 else "b"
        assert all(w.startswith(prefix) for w in text.split())


def test_consecutive_chunks_overlap():
    chunks = chunk([(1, words(1000))])
    assert len(chunks) > 1
    for (_, first), (_, second) in zip(chunks, chunks[1:]):
        tail = first[-150:].split()[1:]  # drop a possibly partial first word
        assert " ".join(tail) in second


def test_full_text_is_covered():
    text = words(1000)
    covered = set()
    for _, piece in chunk([(1, text)]):
        covered.update(piece.split())
    assert covered == set(text.split())


def test_empty_pages_are_skipped():
    assert chunk([(1, "   "), (2, "")]) == []


def test_chunks_start_and_end_on_word_boundaries():
    text = words(1000)
    vocab = set(text.split())
    for _, piece in chunk([(1, text)]):
        tokens = piece.split()
        assert tokens[0] in vocab and tokens[-1] in vocab
