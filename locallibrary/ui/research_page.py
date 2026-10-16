"""Research page: read a shelf book's sources, ask RAG questions, pull in similar sources."""
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer, QUrl
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
                               QStackedWidget, QTextBrowser, QVBoxLayout, QWidget)

from locallibrary import db, ingest, rag, thumbnails
from locallibrary.ui.widgets import (ORIGIN_LABELS, SOURCE, TYPE_LABELS, CoverImage, DropZone, SourceTile,
                                     type_badge)
from locallibrary.workers import run_in_background

SAVE_DELAY_MS = 1000
RESTORE_SETTLE_MS = 300  # the PDF view re-zooms as it is laid out; re-jump after it settles
CITE_SCHEME = "cite"


def citation_url(source_id: int, page: int) -> str:
    return f"{CITE_SCHEME}:{source_id}:{page}"


def parse_citation_url(url: str) -> tuple[int, int] | None:
    scheme, _, rest = url.partition(":")
    source_id, _, page = rest.partition(":")
    if scheme != CITE_SCHEME or not source_id.isdigit() or not page.isdigit():
        return None
    return int(source_id), int(page)


def answer_markdown(answer) -> str:
    lines = [answer.text, ""]
    if answer.citations:
        lines.append("**Where to look**")
        lines.append("")
        for c in answer.citations:
            lines.append(f"- [{c.source_title}, p. {c.page}]({citation_url(c.source_id, c.page)}) — {c.snippet}")
    return "\n".join(lines)


def tile_list(parent_layout: QVBoxLayout, heading: str, object_name: str) -> tuple[QWidget, QVBoxLayout]:
    """A titled, scrollable column for BookTiles. Returns (container, tile layout)."""
    container = QWidget()
    container.setObjectName(object_name)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    title = QLabel(heading)
    title.setObjectName("ColumnHeading")
    layout.addWidget(title)
    inner = QWidget()
    tiles = QVBoxLayout(inner)
    tiles.addStretch()
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(inner)
    layout.addWidget(scroll)
    parent_layout.addWidget(container)
    return container, tiles


def clear_tiles(tiles: QVBoxLayout) -> None:
    while tiles.count() > 1:
        tiles.takeAt(0).widget().deleteLater()


class ResearchPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.setObjectName("ResearchPage")
        self.window_ = window
        self.book = None
        self.sources = []
        self.source = None
        self.page = 1
        self.page_count = 0
        self.sections: list[str] = []  # web article text, one entry per page
        self.load_id = 0
        self.restoring_page: int | None = None  # set while a saved PDF page is being restored
        self.covers: dict[int, str] = {}  # source id -> cached cover image path
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_position)

        root = QVBoxLayout(self)

        # --- top bar ---
        bar = QHBoxLayout()
        back = QPushButton("Back to Library")
        back.setObjectName("BackButton")
        back.clicked.connect(window.show_library)
        self.title = QLabel("")
        self.title.setObjectName("PageHeading")
        self.rag_toggle = QPushButton("RAG query")
        self.rag_toggle.setCheckable(True)
        self.similar_toggle = QPushButton("Similar Sources")
        self.similar_toggle.setCheckable(True)
        bar.addWidget(back)
        bar.addWidget(self.title, 1)
        bar.addWidget(self.rag_toggle)
        bar.addWidget(self.similar_toggle)
        for name in ("Highlighter", "Notepad"):
            button = QPushButton(name)
            button.setEnabled(False)
            button.setToolTip("Coming later")
            bar.addWidget(button)
        root.addLayout(bar)

        body = QHBoxLayout()
        root.addLayout(body, 1)

        # --- left strip: this book's sources ---
        left = QVBoxLayout()
        self.strip, self.strip_tiles = tile_list(left, "Sources", "SourceStrip")
        self.strip.setFixedWidth(210)
        body.addLayout(left)

        # --- center: "Now reading" bar, viewer, nav bar, RAG panel ---
        center = QVBoxLayout()
        self.now_reading = QFrame()
        self.now_reading.setObjectName("NowReading")
        now = QHBoxLayout(self.now_reading)
        now.setContentsMargins(8, 6, 8, 6)
        self.now_cover_slot = QHBoxLayout()
        self.now_cover = None
        now.addLayout(self.now_cover_slot)
        now_text = QVBoxLayout()
        now_text.setSpacing(2)
        self.now_badge_slot = QHBoxLayout()
        self.now_title = QLabel("")
        self.now_title.setObjectName("NowReadingTitle")
        self.now_title.setWordWrap(True)
        self.now_meta = QLabel("")
        self.now_meta.setObjectName("NowReadingMeta")
        now_text.addLayout(self.now_badge_slot)
        now_text.addWidget(self.now_title)
        now_text.addWidget(self.now_meta)
        now.addLayout(now_text, 1)
        self.now_reading.hide()
        center.addWidget(self.now_reading)
        self.viewer_zone = DropZone(SOURCE, "")
        self.viewer_zone.setObjectName("ViewerZone")
        self.viewer_zone.placeholder.hide()
        self.viewer_zone.dropped.connect(self.add_similar_source)
        self.viewer_stack = QStackedWidget()
        self.pdf_doc = QPdfDocument(self)
        self.pdf_view = QPdfView()
        self.pdf_view.setDocument(self.pdf_doc)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.pdf_view.pageNavigator().currentPageChanged.connect(self._pdf_page_changed)
        self.pdf_view.installEventFilter(self)
        self.text_view = QTextBrowser()
        self.text_view.setObjectName("ArticleView")
        self.message = QLabel("")
        self.message.setObjectName("ViewerMessage")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        for widget in (self.pdf_view, self.text_view, self.message):
            self.viewer_stack.addWidget(widget)
        self.viewer_zone.content.addWidget(self.viewer_stack)
        center.addWidget(self.viewer_zone, 1)

        nav = QHBoxLayout()
        self.prev_button = QPushButton("◀ Prev")
        self.prev_button.clicked.connect(lambda: self.go_to_page(self.page - 1))
        self.page_box = QSpinBox()
        self.page_box.setMinimum(1)
        self.page_box.setKeyboardTracking(False)
        self.page_box.valueChanged.connect(self.go_to_page)
        self.page_total = QLabel("")
        self.next_button = QPushButton("Next ▶")
        self.next_button.clicked.connect(lambda: self.go_to_page(self.page + 1))
        self.status = QLabel("")
        self.status.setObjectName("StatusText")
        nav.addWidget(self.prev_button)
        nav.addWidget(QLabel("Page"))
        nav.addWidget(self.page_box)
        nav.addWidget(self.page_total)
        nav.addWidget(self.next_button)
        nav.addWidget(self.status, 1)
        center.addLayout(nav)

        self.rag_panel = QWidget()
        self.rag_panel.setObjectName("RagPanel")
        rag_layout = QVBoxLayout(self.rag_panel)
        ask_row = QHBoxLayout()
        self.question_box = QLineEdit()
        self.question_box.setObjectName("QuestionBox")
        self.question_box.setPlaceholderText("Type your question here!")
        self.question_box.returnPressed.connect(self.ask)
        self.ask_button = QPushButton("Ask")
        self.ask_button.clicked.connect(self.ask)
        ask_row.addWidget(self.question_box, 1)
        ask_row.addWidget(self.ask_button)
        self.answer_view = QTextBrowser()
        self.answer_view.setObjectName("RagAnswer")
        self.answer_view.setOpenLinks(False)
        self.answer_view.anchorClicked.connect(self._citation_clicked)
        self.answer_view.setMinimumHeight(180)
        rag_layout.addLayout(ask_row)
        rag_layout.addWidget(self.answer_view)
        self.rag_panel.hide()
        center.addWidget(self.rag_panel)
        body.addLayout(center, 1)
        self.rag_toggle.toggled.connect(self.rag_panel.setVisible)

        # --- right: similar sources ---
        right = QVBoxLayout()
        self.similar_panel, self.similar_tiles = tile_list(right, "Similar Sources", "SimilarPanel")
        self.similar_panel.setFixedWidth(230)
        self.similar_hint = QLabel("Drag one onto the page to add it.")
        self.similar_hint.setObjectName("ColumnMessage")
        self.similar_hint.setWordWrap(True)
        self.similar_panel.layout().insertWidget(1, self.similar_hint)
        self.similar_panel.hide()
        body.addLayout(right)
        self.similar_toggle.toggled.connect(self._similar_toggled)

    # --- loading -----------------------------------------------------------

    def load(self, shelf_book_id: int) -> None:
        self.load_id += 1
        self.book = db.get_shelf_book(shelf_book_id)
        if self.book is None:
            self.title.setText("")
            self._show_message("This shelf book no longer exists.")
            return
        self.title.setText(self.book.title)
        self.answer_view.clear()
        self.question_box.clear()
        self.status.setText("")
        self._reload_sources()
        start = self.book.last_source_id if self.book.last_source_id in self.book.source_ids else None
        start = start or (self.book.source_ids[0] if self.book.source_ids else None)
        if start is None:
            self._show_message("This shelf book has no sources yet.")
            return
        self.open_source(start, self.book.last_page if start == self.book.last_source_id else 1, save=False)

    def _reload_sources(self) -> None:
        self.book = db.get_shelf_book(self.book.id)
        self.sources = db.get_sources(self.book.source_ids)
        clear_tiles(self.strip_tiles)
        for source in self.sources:
            tile = SourceTile(source)
            tile.clicked.connect(lambda sid: self.open_source(sid, 1))
            tile.set_cover(self.covers.get(source.id))
            self.strip_tiles.insertWidget(self.strip_tiles.count() - 1, tile)
        self._highlight_strip()
        self._load_covers(self.sources)

    def _load_covers(self, sources) -> None:
        """Render missing covers in the background, then show them on every tile and the Now-reading bar."""
        missing = [s for s in sources if s.id not in self.covers and s.downloaded]
        if not missing:
            return
        load_id = self.load_id

        def done(found: dict) -> None:
            self.covers.update(found)
            if load_id != self.load_id:
                return
            for tiles in (self.strip_tiles, self.similar_tiles):
                for i in range(tiles.count() - 1):
                    tile = tiles.itemAt(i).widget()
                    if tile.item_id in found:
                        tile.set_cover(found[tile.item_id])
            if self.source and self.source.id in found and self.now_cover:
                self.now_cover.set_cover(found[self.source.id])

        run_in_background(thumbnails.cover_paths, missing, on_done=done)

    def _update_now_reading(self, rebuild: bool = False) -> None:
        if not self.source:
            self.now_reading.hide()
            return
        if rebuild or self.now_cover is None:
            for slot in (self.now_cover_slot, self.now_badge_slot):
                while slot.count():
                    item = slot.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
            self.now_cover = CoverImage(self.source.source_type, 36, 48)
            self.now_cover.set_cover(self.covers.get(self.source.id))
            self.now_cover_slot.addWidget(self.now_cover)
            self.now_badge_slot.addWidget(type_badge(self.source.source_type))
            self.now_badge_slot.addStretch()
            self.now_title.setText(self.source.title)
        origin = ORIGIN_LABELS.get(self.source.origin, self.source.origin)
        unit = "Section" if self.viewer_stack.currentWidget() is self.text_view else "Page"
        where = f"{unit} {self.page} of {self.page_count}" if self.page_count else "Not readable here"
        self.now_meta.setText(f"Now reading · {TYPE_LABELS.get(self.source.source_type, '')} · {origin} · {where}")
        self.now_reading.show()

    def _highlight_strip(self) -> None:
        for i in range(self.strip_tiles.count() - 1):
            tile = self.strip_tiles.itemAt(i).widget()
            tile.setProperty("selected", bool(self.source and tile.item_id == self.source.id))
            tile.style().unpolish(tile)
            tile.style().polish(tile)

    def _show_message(self, text: str) -> None:
        self.message.setText(text)
        self.viewer_stack.setCurrentWidget(self.message)
        self.page_count = 0
        self._update_nav()

    def open_source(self, source_id: int, page: int = 1, save: bool = True) -> None:
        if self.source and self.source.id == source_id:
            self.go_to_page(page)
            return
        source = next((s for s in self.sources if s.id == source_id), None) or db.get_source(source_id)
        if source is None:
            return
        self.source = source
        self._highlight_strip()
        self._update_now_reading(rebuild=True)
        path = Path(source.local_path) if source.local_path else None
        if not path or not path.exists():
            self._show_message(f"“{source.title}” hasn't been downloaded.")
            return
        if ingest.is_pdf(path):
            self.pdf_doc.load(str(path))
            if self.pdf_doc.status() != QPdfDocument.Status.Ready:
                self._show_message(f"Couldn't open the PDF for “{source.title}”.")
                return
            self.sections = []
            self.page_count = self.pdf_doc.pageCount()
            self.viewer_stack.setCurrentWidget(self.pdf_view)
            # Layout and FitToWidth zoom change the scroll position after the first jump, which would
            # report (and save) the wrong page. Ignore page signals until it settles, then jump again.
            self.restoring_page = max(1, min(page, self.page_count))
            QTimer.singleShot(RESTORE_SETTLE_MS, self._finish_restore)
        else:
            self.pdf_doc.close()
            self.sections = [text for _, text in ingest.extract(source)]
            self.page_count = len(self.sections)
            self.viewer_stack.setCurrentWidget(self.text_view)
        self.page = 0  # force go_to_page to render
        self.go_to_page(page, save=save)
        if self.similar_toggle.isChecked():
            self.load_similar()

    # --- pages + saving ----------------------------------------------------

    def go_to_page(self, page: int, save: bool = True) -> None:
        if not self.source or not self.page_count:
            return
        page = max(1, min(int(page), self.page_count))
        if self.restoring_page is not None:
            self.restoring_page = page
        changed = page != self.page
        self.page = page
        if self.viewer_stack.currentWidget() is self.pdf_view:
            navigator = self.pdf_view.pageNavigator()
            if navigator.currentPage() != page - 1:
                navigator.jump(page - 1, QPointF(), navigator.currentZoom())
        elif self.viewer_stack.currentWidget() is self.text_view and changed:
            self.text_view.setPlainText(self.sections[page - 1])
        self._update_nav()
        if changed and save:
            self.save_timer.start(SAVE_DELAY_MS)

    def eventFilter(self, obj, event):
        # FitToWidth re-zooms on resize but keeps the pixel scroll offset, which lands on another page.
        # Keep the reader's page instead.
        if obj is self.pdf_view and event.type() == QEvent.Type.Resize and self.page_count:
            if self.viewer_stack.currentWidget() is self.pdf_view and self.restoring_page is None:
                self.restoring_page = self.page
                QTimer.singleShot(RESTORE_SETTLE_MS, self._finish_restore)
        return super().eventFilter(obj, event)

    def _finish_restore(self) -> None:
        page, self.restoring_page = self.restoring_page, None
        if page and self.viewer_stack.currentWidget() is self.pdf_view:
            navigator = self.pdf_view.pageNavigator()
            navigator.jump(page - 1, QPointF(), navigator.currentZoom())
            self.page = page
            self._update_nav()

    def _pdf_page_changed(self, index: int) -> None:
        if self.restoring_page is not None:
            return
        if self.viewer_stack.currentWidget() is self.pdf_view and index + 1 != self.page:
            self.page = index + 1
            self._update_nav()
            self.save_timer.start(SAVE_DELAY_MS)

    def _update_nav(self) -> None:
        has_pages = self.page_count > 0
        for widget in (self.prev_button, self.next_button, self.page_box):
            widget.setEnabled(has_pages)
        self.page_box.blockSignals(True)
        self.page_box.setMaximum(max(1, self.page_count))
        self.page_box.setValue(self.page if has_pages else 1)
        self.page_box.blockSignals(False)
        self.page_total.setText(f"of {self.page_count}" if has_pages else "")
        self._update_now_reading()

    def save_position(self) -> None:
        self.save_timer.stop()
        if self.book and self.source and self.page_count:
            db.save_position(self.book.id, self.source.id, self.page)

    def on_leave(self) -> None:
        self.save_position()
        self.load_id += 1  # ignore late results from workers started on this page
        self.source = None
        self.pdf_doc.close()

    # --- RAG ---------------------------------------------------------------

    def ask(self) -> None:
        question = self.question_box.text().strip()
        if not question or not self.book:
            return
        load_id = self.load_id
        self.ask_button.setEnabled(False)
        self.answer_view.setPlainText("Thinking…")

        def done(answer):
            if load_id == self.load_id:
                self.ask_button.setEnabled(True)
                self.answer_view.setMarkdown(answer_markdown(answer))

        def failed(message):
            if load_id == self.load_id:
                self.ask_button.setEnabled(True)
                self.answer_view.setPlainText(f"Couldn't answer: {message}")

        run_in_background(rag.ask, question, list(self.book.source_ids), on_done=done, on_error=failed)

    def _citation_clicked(self, url: QUrl) -> None:
        target = parse_citation_url(url.toString())
        if target:
            self.open_source(*target)

    # --- similar sources ---------------------------------------------------

    def _similar_toggled(self, shown: bool) -> None:
        self.similar_panel.setVisible(shown)
        if shown:
            self.load_similar()

    def load_similar(self) -> None:
        if not self.source or not self.book:
            return
        load_id, source_id = self.load_id, self.source.id
        clear_tiles(self.similar_tiles)
        self.similar_hint.setText("Looking for similar sources…")

        def done(found):
            if load_id != self.load_id or not self.source or self.source.id != source_id:
                return
            clear_tiles(self.similar_tiles)
            for source in found:
                tile = SourceTile(source)
                tile.set_cover(self.covers.get(source.id))
                tile.setToolTip(f"{tile.toolTip()}\n\n{source.description[:300]}")
                self.similar_tiles.insertWidget(self.similar_tiles.count() - 1, tile)
            self._load_covers(found)
            self.similar_hint.setText("Drag one onto the page to add it." if found else "No similar sources found.")

        run_in_background(rag.similar_sources, source_id, exclude_ids=list(self.book.source_ids),
                          on_done=done, on_error=lambda msg: self.similar_hint.setText(f"Couldn't load: {msg}"))

    def add_similar_source(self, source_id: int) -> None:
        if not self.book:
            return
        if source_id in self.book.source_ids:
            self.open_source(source_id)
            return
        source = db.get_source(source_id)
        if source is None:
            return
        load_id, book_id = self.load_id, self.book.id

        def done(result):
            db.add_source_to_shelf_book(book_id, result.id)
            if load_id != self.load_id:
                return
            self.status.setText(f"Added “{result.title}”.")
            self._reload_sources()
            self.open_source(result.id, 1)

        def failed(message):
            if load_id == self.load_id:
                self.status.setText(f"Couldn't add “{source.title}”: {message}")

        if source.downloaded:
            done(source)
            return
        self.status.setText(f"Downloading “{source.title}”…")
        run_in_background(ingest.ingest, source, on_done=done, on_error=failed,
                          on_progress=lambda pct, msg: load_id == self.load_id and self.status.setText(
                              f"Adding “{source.title}”: {msg} ({pct}%)"))
