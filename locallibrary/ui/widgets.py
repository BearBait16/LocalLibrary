"""Reusable drag-and-drop widgets: BookTile, BookSpine, SourceSpine, SourceShelf, DropZone, ShelfRow."""
import html

from PySide6.QtCore import QMimeData, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QDrag, QFontMetrics, QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from locallibrary.looks import source_look

MIME_TYPE = "application/x-locallibrary"
SHELF_BOOK = "shelf_book"
SOURCE = "source"

TYPE_LABELS = {"textbook": "Textbook", "research_paper": "Research paper", "web_article": "Web article"}
TYPE_INITIALS = {"textbook": "T", "research_paper": "P", "web_article": "W"}
ORIGIN_LABELS = {"openstax": "OpenStax", "openalex": "OpenAlex", "gemini": "Found by Gemini", "local": "Added by you"}


class CoverImage(QLabel):
    """A source's cover picture, or a placeholder with the type's initial (colored by style.qss)."""

    def __init__(self, source_type: str, width: int, height: int, parent=None):
        super().__init__(parent)
        self.setObjectName("SourceCover")
        self.setFixedSize(width, height)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setProperty("sourceType", source_type)
        self.source_type = source_type
        self.set_cover(None)

    def set_cover(self, path: str | None) -> None:
        pixmap = QPixmap(path) if path else QPixmap()
        if pixmap.isNull():
            self.setPixmap(QPixmap())
            self.setText(TYPE_INITIALS.get(self.source_type, "?"))
            self.setProperty("placeholder", True)
        else:
            self.setText("")
            self.setPixmap(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
            self.setProperty("placeholder", False)
        self.style().unpolish(self)
        self.style().polish(self)


def type_badge(source_type: str) -> QLabel:
    badge = QLabel(TYPE_LABELS.get(source_type, source_type))
    badge.setObjectName("SourceBadge")
    badge.setProperty("sourceType", source_type)
    return badge


def encode(kind: str, item_id: int) -> QMimeData:
    mime = QMimeData()
    mime.setData(MIME_TYPE, f"{kind}:{item_id}".encode())
    return mime


def decode(mime: QMimeData) -> tuple[str, int] | None:
    if not mime.hasFormat(MIME_TYPE):
        return None
    kind, _, item_id = bytes(mime.data(MIME_TYPE)).decode().partition(":")
    return (kind, int(item_id)) if item_id.isdigit() else None


class BookTile(QFrame):
    """A draggable tile showing a title. Drags carry (kind, id)."""

    clicked = Signal(int)
    double_clicked = Signal(int)

    def __init__(self, kind: str, item_id: int, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("BookTile")
        self.kind, self.item_id, self.title = kind, item_id, title
        self.setToolTip(title)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._press_pos: QPoint | None = None
        self.layout_ = QVBoxLayout(self)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("TileTitle")
        self.title_label.setWordWrap(True)
        self.layout_.addWidget(self.title_label)

    def set_title(self, title: str) -> None:
        self.title = title
        self.title_label.setText(title)
        self.setToolTip(title)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_pos is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < QApplication.startDragDistance():
            return
        self._press_pos = None
        drag = QDrag(self)
        drag.setMimeData(encode(self.kind, self.item_id))
        drag.setPixmap(self.grab())
        drag.exec(Qt.DropAction.CopyAction)

    def mouseReleaseEvent(self, event):
        if self._press_pos is not None and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item_id)
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.item_id)


def fit_text(text: str, metrics: QFontMetrics, width: int, height: int) -> str:
    """Drop words from the end (adding "…") until the word-wrapped text fits in width x height."""
    def fits(candidate: str) -> bool:
        flags = int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap)
        rect = metrics.boundingRect(QRect(0, 0, width, 100000), flags, candidate)
        return rect.height() <= height and rect.width() <= width

    # A single word wider than the spine can't wrap; shorten just that word.
    words = [w if metrics.horizontalAdvance(w) <= width else metrics.elidedText(w, Qt.TextElideMode.ElideRight, width)
             for w in text.split()]
    text = " ".join(words)
    if fits(text):
        return text
    while len(words) > 1:
        words.pop()
        candidate = " ".join(words) + "…"
        if fits(candidate):
            return candidate
    return metrics.elidedText(text, Qt.TextElideMode.ElideRight, width)


class BookSpine(BookTile):
    """A shelf book drawn as a spine. Color and design come from style.qss via the
    `spineColor` / `spineDesign` properties; the design's parts are child frames."""

    # Room for the title (width, height in px) inside each design on a 76 x 160 spine.
    TITLE_ROOM = {"bands": (66, 104), "label": (58, 100), "two_tone": (72, 76), "ribbed": (66, 90)}

    def __init__(self, item_id: int, title: str, color: int = 0, design: str = "bands", parent=None):
        super().__init__(SHELF_BOOK, item_id, title, parent)
        self.setObjectName("ShelfSpine")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_.setSpacing(3)
        self.set_look(color, design)

    def set_look(self, color: int, design: str) -> None:
        self.color, self.design = color, design
        self.setProperty("spineColor", str(color))
        self.setProperty("spineDesign", design)
        self.layout_.setContentsMargins(4, 6, 4, 6)
        self.title_label.setParent(self)  # take the title out of the old design's parts first
        while self.layout_.count():
            widget = self.layout_.takeAt(0).widget()
            if widget is not None and widget is not self.title_label:
                widget.deleteLater()
        getattr(self, f"_design_{design}", self._design_bands)()
        self.title_label.show()
        for widget in [self, *self.findChildren(QWidget)]:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        width, height = self.TITLE_ROOM.get(design, self.TITLE_ROOM["bands"])
        self.title_label.setText(fit_text(self.title, QFontMetrics(self.title_label.font()), width, height))
        self.setToolTip(self.title)

    def set_title(self, title: str) -> None:
        self.title = title
        self.set_look(self.color, self.design)

    def _part(self, name: str, edge: str = "") -> QFrame:
        part = QFrame()
        part.setObjectName(name)
        if edge:
            part.setProperty("edge", edge)
        return part

    def _add_parts(self, name: str, count: int) -> None:
        for _ in range(count):
            self.layout_.addWidget(self._part(name))

    def _design_bands(self) -> None:
        self.layout_.addSpacing(8)
        self._add_parts("SpineBand", 2)
        self.layout_.addStretch()
        self.layout_.addWidget(self.title_label)
        self.layout_.addStretch()
        self._add_parts("SpineBand", 2)
        self.layout_.addSpacing(8)

    def _design_label(self) -> None:
        label = self._part("SpineLabel")
        inner = QVBoxLayout(label)
        inner.setContentsMargins(2, 6, 2, 6)
        inner.addWidget(self.title_label)
        self.layout_.addStretch()
        self.layout_.addWidget(label)
        self.layout_.addStretch()

    def _design_two_tone(self) -> None:
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.addWidget(self._part("SpineTone", "top"))
        self.layout_.addStretch()
        self.layout_.addWidget(self.title_label)
        self.layout_.addStretch()
        self.layout_.addWidget(self._part("SpineTone", "bottom"))

    def _design_ribbed(self) -> None:
        self.layout_.addSpacing(10)
        self._add_parts("SpineRib", 2)
        self.layout_.addStretch()
        self.layout_.addWidget(self.title_label)
        self.layout_.addStretch()
        self._add_parts("SpineRib", 2)
        self.layout_.addSpacing(10)


TYPE_CAP_ROOM = 18  # px of title room a source spine's type cap takes


class SourceSpine(BookSpine):
    """A source drawn as a book spine: design from its type, color from its id, and a type cap at the
    bottom. Picks also get a remove button and show download progress / errors on the spine."""

    remove_requested = Signal(int)
    TYPE_CAPS = {"textbook": "TEXTBOOK", "research_paper": "PAPER", "web_article": "WEB"}
    TITLE_ROOM = {design: (w, h - TYPE_CAP_ROOM) for design, (w, h) in BookSpine.TITLE_ROOM.items()}

    def __init__(self, source, reason: str = "", removable: bool = False, parent=None):
        self.source, self.reason = source, reason
        self.cover_path: str | None = None
        self.status = ""
        color, design = source_look(source.id, source.source_type)
        super().__init__(source.id, source.title, color, design, parent)
        self.kind = SOURCE
        self.progress_bar = QProgressBar(self)  # positioned by hand over the bottom of the spine
        self.progress_bar.setObjectName("SpineProgress")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        self.remove_button = None
        if removable:
            self.remove_button = QPushButton("✕", self)
            self.remove_button.setObjectName("SpineRemove")
            self.remove_button.setToolTip("Remove")
            self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self.item_id))
        self._update_tooltip()

    def set_look(self, color: int, design: str) -> None:
        super().set_look(color, design)
        cap = QLabel(self.TYPE_CAPS.get(self.source.source_type, "SOURCE"))
        cap.setObjectName("SpineTypeCap")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap.setProperty("sourceType", self.source.source_type)
        self.layout_.addWidget(cap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.progress_bar.setGeometry(5, self.height() - 26, self.width() - 10, 6)
        if self.remove_button:
            self.remove_button.setGeometry(self.width() - 22, 3, 19, 19)

    def set_cover(self, path: str | None) -> None:
        self.cover_path = path
        self._update_tooltip()

    def set_progress(self, percent: int, message: str) -> None:
        self.progress_bar.show()
        self.progress_bar.setValue(percent)
        self.status = message
        self._update_tooltip()

    def set_status(self, message: str, error: bool = False) -> None:
        self.progress_bar.hide()
        self.status = message
        self.setProperty("error", error)
        self.style().unpolish(self)
        self.style().polish(self)
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        source = self.source
        parts = []
        if self.cover_path:
            parts.append(f'<img src="{html.escape(self.cover_path)}" height="140"><br>')
        parts.append(f"<b>{html.escape(source.title)}</b><br>{TYPE_LABELS.get(source.source_type, '')} · "
                     f"{html.escape(ORIGIN_LABELS.get(source.origin, source.origin))}")
        if self.status:
            parts.append(f"<br>{html.escape(self.status)}")
        if self.reason:
            parts.append(f"<br><br><i>{html.escape(self.reason)}</i>")
        self.setToolTip(f"<qt>{''.join(parts)}</qt>")


def shelf_slots(count: int, width: int) -> list[tuple[int, int]]:
    """Top-left corner of each spine on a SourceShelf `width` px wide: left to right, then the next shelf down."""
    per_row = max(1, (width - 2 * SourceShelf.MARGIN) // SourceShelf.SLOT_WIDTH)
    return [(SourceShelf.MARGIN + (i % per_row) * SourceShelf.SLOT_WIDTH,
             (i // per_row) * SourceShelf.ROW_HEIGHT + SourceShelf.TOP)
            for i in range(count)]


class SourceShelf(QWidget):
    """Source spines standing on as many shelves as they need. Goes inside a QScrollArea."""

    SPINE_SIZE = (76, 160)  # matches QFrame#ShelfSpine in style.qss
    SLOT_WIDTH = 84
    MARGIN = 6
    TOP = 6
    BOARD_HEIGHT = 10
    ROW_HEIGHT = 186  # top gap + spine + board + gap to the next shelf

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SourceShelf")
        self._spines: list[SourceSpine] = []
        self._boards: list[QFrame] = []
        self._relayout()

    def spines(self) -> list[SourceSpine]:
        return list(self._spines)

    def add(self, spine: SourceSpine) -> None:
        spine.setParent(self)
        self._spines.append(spine)
        spine.show()
        self._relayout()

    def remove(self, spine: SourceSpine) -> None:
        if spine in self._spines:
            self._spines.remove(spine)
            spine.setParent(None)
            self._relayout()

    def clear(self) -> None:
        for spine in self._spines:
            spine.deleteLater()
        self._spines.clear()
        self._relayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        slots = shelf_slots(len(self._spines), self.width())
        rows = max(1, (slots[-1][1] // self.ROW_HEIGHT + 1) if slots else 1)
        while len(self._boards) < rows:
            board = QFrame(self)
            board.setObjectName("SourceShelfBoard")
            board.show()
            self._boards.append(board)
        while len(self._boards) > rows:
            self._boards.pop().deleteLater()
        width, height = self.SPINE_SIZE
        for row, board in enumerate(self._boards):
            board.setGeometry(0, row * self.ROW_HEIGHT + self.TOP + height, self.width(), self.BOARD_HEIGHT)
            board.lower()
        for spine, (x, y) in zip(self._spines, slots):
            spine.setGeometry(x, y, width, height)
        self.setMinimumHeight(rows * self.ROW_HEIGHT)


class DropZone(QFrame):
    """Accepts drops of one kind and emits dropped(id). Child widgets go in `content`."""

    dropped = Signal(int)

    def __init__(self, kind: str, placeholder: str = "Drag here!", parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.kind = kind
        self.setAcceptDrops(True)
        self.content = QVBoxLayout(self)
        self.placeholder = QLabel(placeholder)
        self.placeholder.setObjectName("DropPlaceholder")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content.addWidget(self.placeholder)

    def _accepts(self, mime: QMimeData) -> int | None:
        decoded = decode(mime)
        return decoded[1] if decoded and decoded[0] == self.kind else None

    def _set_hover(self, hover: bool) -> None:
        self.setProperty("dragOver", hover)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):
        if self._accepts(event.mimeData()) is not None:
            event.acceptProposedAction()
            self._set_hover(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._accepts(event.mimeData()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_hover(False)

    def dropEvent(self, event):
        self._set_hover(False)
        item_id = self._accepts(event.mimeData())
        if item_id is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self.dropped.emit(item_id)


def insertion_index(centers: list[float], x: float) -> int:
    """Where a book dropped at `x` lands among books whose horizontal centers are `centers`."""
    return sum(1 for c in centers if c < x)


class ShelfRow(QFrame):
    """One shelf of the bookcase. Accepts dragged shelf books, shows where they'll land,
    and emits book_dropped(book_id, index). A full shelf only accepts its own books (reordering)."""

    book_dropped = Signal(int, int)
    MARKER_WIDTH = 4
    SLOT_WIDTH = 84  # one 76 px spine (style.qss) plus spacing, so a full shelf always fits
    ROW_HEIGHT = 176  # a 160 px spine + row margins + the 10 px shelf board, so empty shelves keep their size

    def __init__(self, shelf_index: int, capacity: int, parent=None):
        super().__init__(parent)
        self.setObjectName("Shelf")
        self.shelf_index, self.capacity = shelf_index, capacity
        self.setAcceptDrops(True)
        self.row = QHBoxLayout(self)
        self.row.setSpacing(self.SLOT_WIDTH - 76)
        self.row.setContentsMargins(6, 4, 6, 2)
        self.row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.setMinimumWidth(capacity * self.SLOT_WIDTH + 24)
        self.setFixedHeight(self.ROW_HEIGHT)
        self.marker = QFrame(self)  # positioned by hand, not in the layout, so spines don't shift during a drag
        self.marker.setObjectName("DropMarker")
        self.marker.hide()

    def spines(self) -> list[BookTile]:
        return [self.row.itemAt(i).widget() for i in range(self.row.count()) if self.row.itemAt(i).widget()]

    def add_spine(self, spine: BookTile) -> None:
        self.row.addWidget(spine)

    def book_ids(self) -> list[int]:
        return [s.item_id for s in self.spines()]

    def accepts(self, book_id: int) -> bool:
        return book_id in self.book_ids() or len(self.book_ids()) < self.capacity

    def _others(self, book_id: int) -> list[BookTile]:
        return [s for s in self.spines() if s.item_id != book_id]

    def drop_index(self, book_id: int, x: float) -> int:
        return insertion_index([s.geometry().center().x() for s in self._others(book_id)], x)

    def _set_state(self, state: str) -> None:
        self.setProperty("dropState", state)
        self.style().unpolish(self)
        self.style().polish(self)

    def _show_marker(self, book_id: int, index: int) -> None:
        others = self._others(book_id)
        if index < len(others):
            x = others[index].geometry().left() - self.MARKER_WIDTH - 1
        elif others:
            x = others[-1].geometry().right() + 2
        else:
            x = self.contentsMargins().left()
        top = others[0].geometry().top() if others else self.contentsMargins().top()
        height = others[0].height() if others else self.height() - top - self.contentsMargins().bottom()
        self.marker.setGeometry(max(0, x), top, self.MARKER_WIDTH, height)
        self.marker.show()
        self.marker.raise_()

    def _drag_book(self, event) -> int | None:
        decoded = decode(event.mimeData())
        return decoded[1] if decoded and decoded[0] == SHELF_BOOK else None

    def dragEnterEvent(self, event):
        self.dragMoveEvent(event)

    def dragMoveEvent(self, event):
        book_id = self._drag_book(event)
        if book_id is None:
            event.ignore()
            return
        if not self.accepts(book_id):
            self._set_state("full")
            self.marker.hide()
            event.ignore()
            return
        self._set_state("over")
        self._show_marker(book_id, self.drop_index(book_id, event.position().x()))
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._set_state("")
        self.marker.hide()

    def dropEvent(self, event):
        self._set_state("")
        self.marker.hide()
        book_id = self._drag_book(event)
        if book_id is None or not self.accepts(book_id):
            event.ignore()
            return
        event.acceptProposedAction()
        self.book_dropped.emit(book_id, self.drop_index(book_id, event.position().x()))
