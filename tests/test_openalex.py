from locallibrary.sources.openalex import rebuild_abstract


def test_rebuild_abstract_orders_words():
    index = {"statistics": [1, 4], "Intro": [0], "to": [2], "is": [3]}
    assert rebuild_abstract(index) == "Intro statistics to is statistics"


def test_rebuild_abstract_empty():
    assert rebuild_abstract(None) == ""
    assert rebuild_abstract({}) == ""
