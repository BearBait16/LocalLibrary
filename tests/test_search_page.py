import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from locallibrary.models import RESEARCH_PAPER, TEXTBOOK, Source
from locallibrary.ui import search_page
from locallibrary.ui.search_page import DOWNLOADING, READY, SearchPage


class FakeWindow:
    def show_library(self): ...


@pytest.fixture
def page(monkeypatch):
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(search_page, "run_in_background", lambda *a, **k: None)  # no real ingest
    p = SearchPage(FakeWindow())
    p.known = {
        1: Source("Book", TEXTBOOK, "openstax", "u1", downloaded=True, id=1),
        2: Source("Paper", RESEARCH_PAPER, "openalex", "u2", downloaded=False, id=2),
    }
    return p


def test_done_disabled_when_empty(page):
    assert not page.done_button.isEnabled()


def test_ready_source_enables_done(page):
    page.add_source(1)
    assert page.state[1] == READY and page.done_button.isEnabled()


def test_downloading_source_blocks_done(page):
    page.add_source(1)
    page.add_source(2)
    assert page.state[2] == DOWNLOADING and not page.done_button.isEnabled()
    page._ingest_done(2, page.chosen[2], page.known[2])
    assert page.done_button.isEnabled() and page.ready_ids() == [1, 2]


def test_failed_source_is_skipped(page):
    page.add_source(1)
    page.add_source(2)
    page._ingest_failed(2, page.chosen[2], "boom")
    assert page.done_button.isEnabled() and page.ready_ids() == [1]


def test_duplicate_drop_ignored_and_remove(page):
    page.add_source(1)
    page.add_source(1)
    assert list(page.chosen) == [1]
    page.remove_source(1)
    assert not page.chosen and not page.done_button.isEnabled()


def test_picks_are_spines_on_the_picks_shelf(page):
    page.add_source(1)
    page.add_source(2)
    assert page.picks.spines() == [page.chosen[1], page.chosen[2]]
    page._ingest_failed(2, page.chosen[2], "boom")
    assert page.chosen[2].property("error") is True and "boom" in page.error.text()
    page.remove_source(2)
    assert page.picks.spines() == [page.chosen[1]]
