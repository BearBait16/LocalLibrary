from locallibrary.sources.gemini_web import parse_results


def test_parses_fenced_json_and_drops_bad_items():
    reply = """Here you go:
```json
[{"title": "Stats guide", "url": "https://example.org/a", "type": "web_article", "reason": "clear"},
 {"title": "No URL", "url": "", "type": "web_article"},
 {"title": "Odd type", "url": "https://example.org/b", "type": "video"}]
```"""
    results = parse_results(reply)
    assert [r["url"] for r in results] == ["https://example.org/a", "https://example.org/b"]
    assert results[1]["type"] == "web_article"


def test_bad_json_returns_empty():
    assert parse_results("sorry, no results") == []
    assert parse_results("[{broken") == []
