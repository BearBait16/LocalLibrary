"""Search page: topic in, recommended sources out, drag the ones you want, Done makes a shelf book."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from locallibrary import db, ingest, recommend
from locallibrary.config import config
from locallibrary.models import TEXTBOOK, Source
from locallibrary.sources import gemini_web
from locallibrary.ui.widgets import SOURCE, DropZone, SourceCard
from locallibrary.workers import run_in_background

READY, DOWNLOADING, FAILED = "ready", "downloading", "failed"


class ResultColumn(QWidget):
    """A heading over a scrollable list of SourceCards."""

    def __init__(self, heading: str):
        super().__init__()
        self.setObjectName("ResultColumn")
        layout = QVBoxLayout(self)
        title = QLabel(heading)
        title.setObjectName("ColumnHeading")
        layout.addWidget(title)
        inner = QWidget()
        inner.setObjectName("ResultList")
        self.cards = QVBoxLayout(inner)
        self.cards.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def clear(self) -> None:
        while self.cards.count() > 1:
            self.cards.takeAt(0).widget().deleteLater()

    def add(self, card: SourceCard) -> None:
        self.cards.insertWidget(self.cards.count() - 1, card)

    def set_message(self, text: str) -> None:
        label = QLabel(text)
        label.setObjectName("ColumnMessage")
        label.setWordWrap(True)
        self.cards.insertWidget(self.cards.count() - 1, label)


class SearchPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.setObjectName("SearchPage")
        self.window_ = window
        self.search_id = 0  # results from an older search are ignored
        self.pending = 0
        self.query = ""
        self.known: dict[int, Source] = {}  # every source shown in the results
        self.chosen: dict[int, SourceCard] = {}  # source id -> card in the drop zone (drop order)
        self.state: dict[int, str] = {}

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        back = QPushButton("Back to Library")
        back.setObjectName("BackButton")
        back.clicked.connect(window.show_library)
        top.addWidget(back)
        top.addStretch()
        layout.addLayout(top)

        heading = QLabel("RESEARCH TIME! What would you like to learn about?")
        heading.setObjectName("PageHeading")
        layout.addWidget(heading)

        row = QHBoxLayout()
        self.query_box = QLineEdit()
        self.query_box.setObjectName("QueryBox")
        self.query_box.setPlaceholderText("e.g. intro to statistics")
        self.query_box.returnPressed.connect(self.start_search)
        self.web_box = QCheckBox("Also search the web with Gemini")
        self.web_box.setObjectName("WebCheckbox")
        self.web_box.setVisible(config.gemini_enabled)
        self.search_button = QPushButton("Search")
        self.search_button.setObjectName("SearchButton")
        self.search_button.clicked.connect(self.start_search)
        row.addWidget(self.query_box, 1)
        row.addWidget(self.web_box)
        row.addWidget(self.search_button)
        layout.addLayout(row)

        status_row = QHBoxLayout()
        self.busy = QProgressBar()
        self.busy.setObjectName("BusyBar")
        self.busy.setRange(0, 0)
        self.busy.setMaximumWidth(160)
        self.busy.hide()
        self.status = QLabel("")
        self.status.setObjectName("StatusText")
        status_row.addWidget(self.busy)
        status_row.addWidget(self.status, 1)
        layout.addLayout(status_row)
        self.error = QLabel("")
        self.error.setObjectName("ErrorMessage")
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)

        body = QHBoxLayout()
        self.local_column = ResultColumn("Here's what you got")
        self.web_column = ResultColumn("Here's what Gemini found")
        self.web_column.hide()
        body.addWidget(self.local_column, 1)
        body.addWidget(self.web_column, 1)

        right = QVBoxLayout()
        self.zone = DropZone(SOURCE, "Drag here!")
        self.zone.dropped.connect(self.add_source)
        self.done_button = QPushButton("Done")
        self.done_button.setObjectName("DoneButton")
        self.done_button.setEnabled(False)
        self.done_button.clicked.connect(self.finish)
        right.addWidget(self.zone, 1)
        right.addWidget(self.done_button)
        body.addLayout(right, 1)
        layout.addLayout(body, 1)

    # --- search -------------------------------------------------------------

    def reset(self) -> None:
        self.search_id += 1
        self.pending = 0
        self.query = ""
        self.query_box.clear()
        self.local_column.clear()
        self.web_column.clear()
        self.web_column.hide()
        for source_id in list(self.chosen):
            self.remove_source(source_id)
        self.known.clear()
        self._set_busy(False)
        self.show_error("")
        self.query_box.setFocus()

    def show_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.setVisible(bool(message))

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.busy.setVisible(busy)
        self.search_button.setEnabled(not busy)
        self.status.setText(message)

    def start_search(self) -> None:
        query = self.query_box.text().strip()
        if not query:
            return
        self.search_id += 1
        search_id = self.search_id
        self.query = query
        self.show_error("")
        self.local_column.clear()
        self.web_column.clear()
        use_web = config.gemini_enabled and self.web_box.isChecked()
        self.web_column.setVisible(use_web)
        self.pending = 2 if use_web else 1
        self._set_busy(True, "Finding sources… (the first search loads Gemma, which can take a minute)")
        run_in_background(recommend.recommend, query,
                          on_done=lambda rec: self._show_recommendation(search_id, rec),
                          on_error=lambda msg: self._search_failed(search_id, "Recommendation failed", msg))
        if use_web:
            run_in_background(gemini_web.find_web_sources, query,
                              on_done=lambda found: self._show_web(search_id, found),
                              on_error=lambda msg: self._search_failed(search_id, "Gemini web search failed", msg))

    def _one_done(self) -> None:
        self.pending -= 1
        if self.pending <= 0:
            self._set_busy(False, "Drag the sources you want into the box, then press Done.")

    def _result_card(self, source: Source, reason: str) -> SourceCard:
        self.known[source.id] = source
        card = SourceCard(source, reason)
        card.double_clicked.connect(self.add_source)
        return card

    def _show_recommendation(self, search_id: int, rec) -> None:
        if search_id != self.search_id:
            return
        sources = ([rec.textbook] if rec.textbook else []) + rec.papers
        for source in sources:
            self.local_column.add(self._result_card(source, rec.reasons.get(source.id, "")))
        if not sources:
            self.local_column.set_message("Nothing found in the library for this topic yet.")
        elif rec.used_fallback:
            self.local_column.set_message("(Gemma was unavailable, so these are ranked by similarity.)")
        self._one_done()

    def _show_web(self, search_id: int, found) -> None:
        if search_id != self.search_id:
            return
        for source, reason in found:
            self.web_column.add(self._result_card(source, reason))
        if not found:
            self.web_column.set_message("Gemini didn't return any usable sources.")
        self._one_done()

    def _search_failed(self, search_id: int, what: str, message: str) -> None:
        if search_id != self.search_id:
            return
        self.show_error(f"{what}: {message}")
        self._one_done()

    # --- drop zone ----------------------------------------------------------

    def add_source(self, source_id: int) -> None:
        if source_id in self.chosen:
            return
        source = self.known.get(source_id) or db.get_source(source_id)
        if source is None:
            return
        self.zone.placeholder.hide()
        card = SourceCard(source, removable=True)
        card.remove_requested.connect(self.remove_source)
        self.zone.content.addWidget(card)
        self.chosen[source_id] = card
        if source.downloaded:
            self.state[source_id] = READY
            card.set_status("Ready")
        else:
            self.state[source_id] = DOWNLOADING
            card.set_progress(0, "Starting download…")
            run_in_background(ingest.ingest, source,
                              on_progress=lambda pct, msg: self._ingest_progress(source_id, card, pct, msg),
                              on_done=lambda result: self._ingest_done(source_id, card, result),
                              on_error=lambda msg: self._ingest_failed(source_id, card, msg))
        self._update_done()

    def _ingest_progress(self, source_id: int, card: SourceCard, percent: int, message: str) -> None:
        if self.chosen.get(source_id) is card:
            card.set_progress(percent, message)

    def _ingest_done(self, source_id: int, card: SourceCard, source: Source) -> None:
        self.known[source_id] = source
        if self.chosen.get(source_id) is card:
            self.state[source_id] = READY
            card.source = source
            card.set_status("Ready")
            self._update_done()

    def _ingest_failed(self, source_id: int, card: SourceCard, message: str) -> None:
        if self.chosen.get(source_id) is card:
            self.state[source_id] = FAILED
            card.set_status(f"Couldn't add this source: {message}", error=True)
            self._update_done()

    def remove_source(self, source_id: int) -> None:
        card = self.chosen.pop(source_id, None)
        self.state.pop(source_id, None)
        if card:
            card.deleteLater()
        if not self.chosen:
            self.zone.placeholder.show()
        self._update_done()

    def ready_ids(self) -> list[int]:
        return [sid for sid in self.chosen if self.state.get(sid) == READY]

    def _update_done(self) -> None:
        downloading = any(s == DOWNLOADING for s in self.state.values())
        self.done_button.setEnabled(bool(self.ready_ids()) and not downloading)

    def finish(self) -> None:
        ids = self.ready_ids()
        if not ids:
            return
        sources = {sid: self.chosen[sid].source for sid in ids}
        first = next((sid for sid in ids if sources[sid].source_type == TEXTBOOK), ids[0])
        title = self.query or sources[first].title
        try:
            book = db.create_shelf_book(title, title, ids, first)
        except db.LibraryFull:
            self.show_error("Your bookcase is full. Delete a book from the Library to make room, then press Done again.")
            return
        except Exception as exc:
            self.show_error(f"Couldn't save the shelf book: {exc}")
            return
        self.window_.open_research(book.id)
