import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication

from locallibrary.ui.widgets import SHELF_BOOK, SOURCE, DropZone, decode, encode


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _drop(zone, mime):
    event = QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier)
    zone.dropEvent(event)
    return event


def _enter(zone, mime):
    event = QDragEnterEvent(QPointF(zone.rect().center()), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                            Qt.KeyboardModifier.NoModifier)
    zone.dragEnterEvent(event)
    return event


def test_mime_round_trip():
    assert decode(encode(SOURCE, 42)) == (SOURCE, 42)


def test_drop_zone_accepts_matching_kind(app):
    zone = DropZone(SOURCE)
    received = []
    zone.dropped.connect(received.append)
    assert _enter(zone, encode(SOURCE, 7)).isAccepted()
    _drop(zone, encode(SOURCE, 7))
    assert received == [7]


def test_drop_zone_rejects_other_kind(app):
    zone = DropZone(SOURCE)
    received = []
    zone.dropped.connect(received.append)
    assert not _enter(zone, encode(SHELF_BOOK, 3)).isAccepted()
    _drop(zone, encode(SHELF_BOOK, 3))
    assert received == []


def test_spine_title_is_shortened_to_fit(app):
    from locallibrary.ui.widgets import BookSpine

    long_title = "Data analyzation and how I can make graphs from my survey results in Python"
    spine = BookSpine(1, long_title, 2, "two_tone")
    shown = spine.title_label.text()
    assert shown.endswith("…") and len(shown) < len(long_title)
    assert spine.toolTip() == long_title
    spine.set_look(2, "bands")  # more room, still the same title underneath
    assert spine.title == long_title
    assert BookSpine(2, "Stats", 0, "label").title_label.text() == "Stats"


def test_shelf_slots_wrap_onto_next_shelf():
    from locallibrary.ui.widgets import SourceShelf, shelf_slots
    slots = shelf_slots(5, 2 * SourceShelf.MARGIN + 2 * SourceShelf.SLOT_WIDTH)
    assert [y for _, y in slots] == [SourceShelf.TOP] * 2 + [SourceShelf.TOP + SourceShelf.ROW_HEIGHT] * 2 + \
        [SourceShelf.TOP + 2 * SourceShelf.ROW_HEIGHT]
    assert slots[0][0] == slots[2][0] == SourceShelf.MARGIN
    assert shelf_slots(3, 10) == [(SourceShelf.MARGIN, SourceShelf.TOP + i * SourceShelf.ROW_HEIGHT) for i in range(3)]


def test_source_spine_drags_as_source_and_shows_status(app):
    from locallibrary.models import Source
    from locallibrary.ui.widgets import SourceShelf, SourceSpine
    spine = SourceSpine(Source("A very long textbook title indeed", "textbook", "openstax", "u", id=4),
                        reason="Good start", removable=True)
    assert decode(encode(spine.kind, spine.item_id)) == (SOURCE, 4)
    assert "Good start" in spine.toolTip() and spine.remove_button is not None
    spine.set_progress(40, "Downloading")
    assert spine.progress_bar.isVisibleTo(spine) and spine.progress_bar.value() == 40
    spine.set_status("Couldn't add", error=True)
    assert not spine.progress_bar.isVisibleTo(spine) and spine.property("error") is True
    shelf = SourceShelf()
    shelf.resize(400, 300)
    shelf.add(spine)
    assert shelf.spines() == [spine] and spine.parent() is shelf
    shelf.remove(spine)
    assert shelf.spines() == []
