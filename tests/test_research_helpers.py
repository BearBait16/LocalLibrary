from locallibrary.rag import Answer, Citation
from locallibrary.ui.research_page import answer_markdown, citation_url, parse_citation_url


def test_citation_url_round_trip():
    assert parse_citation_url(citation_url(12, 340)) == (12, 340)


def test_parse_rejects_other_links():
    assert parse_citation_url("https://example.org") is None
    assert parse_citation_url("cite:x:1") is None


def test_answer_markdown_lists_citations():
    md = answer_markdown(Answer("Look at [1].", [Citation(3, "Stats", 56, "snippet")]))
    assert "[Stats, p. 56](cite:3:56)" in md
