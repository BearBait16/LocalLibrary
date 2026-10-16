import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QApplication

from locallibrary.ui.widgets import SOURCE, BookSpine, ShelfRow, encode, insertion_index


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_insertion_index():
    assert insertion_index([], 50) == 0
    assert insertion_index([40, 120, 200], 10) == 0
    assert insertion_index([40, 120, 200], 130) == 2
    assert insertion_index([40, 120, 200], 999) == 3


def make_row(ids, capacity=3):
    row = ShelfRow(0, capacity)
    for i in ids:
        row.add_spine(BookSpine(i, f"Book {i}"))
    row.resize(row.minimumWidth(), 200)
    row.show()
    QApplication.processEvents()
    return row


def drop(row, kind, book_id, x):
    mime = encode(kind, book_id)  # keep a reference: QDropEvent doesn't own its mime data
    event = QDropEvent(QPointF(x, 50), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier)
    row.dropEvent(event)
    return event


def test_drop_reports_index_among_other_books(app):
    row = make_row([1, 2, 3])
    got = []
    row.book_dropped.connect(lambda b, i: got.append((b, i)))
    first, second = row.spines()[0].geometry(), row.spines()[1].geometry()
    drop(row, "shelf_book", 3, first.left() + 1)  # own book to the front
    drop(row, "shelf_book", 1, second.center().x() + 5)  # past book 2, ignoring book 1 itself
    assert got == [(3, 0), (1, 1)]


def test_full_row_rejects_other_shelves_books_but_allows_reorder(app):
    row = make_row([1, 2, 3])
    got = []
    row.book_dropped.connect(lambda b, i: got.append((b, i)))
    drop(row, "shelf_book", 9, 5)
    mime = encode("shelf_book", 9)
    move = QDragMoveEvent(QPointF(5, 50), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                          Qt.KeyboardModifier.NoModifier)
    row.dragMoveEvent(move)
    assert not move.isAccepted() and row.property("dropState") == "full"
    drop(row, "shelf_book", 2, 5)
    drop(row, SOURCE, 2, 5)  # sources can't go on shelves
    assert got == [(2, 0)]
