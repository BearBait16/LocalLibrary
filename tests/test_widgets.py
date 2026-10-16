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
