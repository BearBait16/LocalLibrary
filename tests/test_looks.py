from locallibrary.looks import SPINE_COLORS, SPINE_DESIGNS, pick_look


def test_first_book_gets_first_look():
    assert pick_look([]) == (0, SPINE_DESIGNS[0])


def test_least_used_and_never_matches_neighbor():
    existing = [(0, "bands"), (1, "label")]
    color, design = pick_look(existing, neighbor=(1, "label"))
    assert color == 2 and design == "two_tone"


def test_neighbor_avoided_even_when_least_used():
    existing = [(c, d) for c in range(len(SPINE_COLORS)) for d in SPINE_DESIGNS if c != 3]
    color, design = pick_look(existing, neighbor=(3, "bands"))
    assert color != 3 and design != "bands"


def test_sequence_of_books_all_differ_from_left_neighbor():
    looks = []
    for _ in range(20):
        looks.append(pick_look(looks, looks[-1] if looks else None))
    assert all(a[0] != b[0] and a[1] != b[1] for a, b in zip(looks, looks[1:]))
