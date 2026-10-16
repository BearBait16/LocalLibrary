import dataclasses

import pymupdf

from locallibrary import config as config_module
from locallibrary import thumbnails
from locallibrary.models import TEXTBOOK, WEB_ARTICLE, Source


def make_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=400)
    page.insert_text((40, 80), "Cover page")
    doc.save(path)


def test_cover_rendered_once_and_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbnails, "config", dataclasses.replace(config_module.config, data_dir=tmp_path))
    pdf = tmp_path / "book.pdf"
    make_pdf(pdf)
    source = Source("Book", TEXTBOOK, "local", "u", local_path=str(pdf), downloaded=True, id=5)
    first = thumbnails.cover_path(source)
    assert first == tmp_path / "thumbnails" / "5.png" and first.read_bytes()[:4] == b"\x89PNG"
    mtime = first.stat().st_mtime_ns
    assert thumbnails.cover_path(source) == first and first.stat().st_mtime_ns == mtime  # cached
    assert pymupdf.open(first).page_count == 1


def test_no_cover_for_html_or_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbnails, "config", dataclasses.replace(config_module.config, data_dir=tmp_path))
    html = tmp_path / "a.html"
    html.write_text("<html><body>hi</body></html>")
    assert thumbnails.cover_path(Source("A", WEB_ARTICLE, "gemini", "u", local_path=str(html), id=1)) is None
    assert thumbnails.cover_path(Source("B", TEXTBOOK, "openstax", "u2", id=2)) is None
    assert thumbnails.cover_paths([Source("B", TEXTBOOK, "openstax", "u2", id=2)]) == {}
