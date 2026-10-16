"""Library page: saved research sessions as books on a bookcase of shelves."""
import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QMenu, QMessageBox,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from locallibrary import db
from locallibrary.config import SHELF_CAPACITY, SHELF_COUNT, config, load_settings, save_settings
from locallibrary.ui.look_dialog import SpineLookDialog
from locallibrary.ui.widgets import SHELF_BOOK, BookSpine, BookTile, DropZone, ShelfRow

class LibraryPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.setObjectName("LibraryPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.window_ = window
        self.background: QPixmap | None = None

        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        heading = QLabel("My Library")
        heading.setObjectName("PageHeading")
        self.new_button = QPushButton("New research")
        self.new_button.setObjectName("NewResearchButton")
        self.new_button.clicked.connect(window.show_search)
        self.background_button = QPushButton("Change background…")
        self.background_button.clicked.connect(self.choose_background)
        self.clear_background_button = QPushButton("Clear background")
        self.clear_background_button.clicked.connect(lambda: self.set_background(None))
        bar.addWidget(heading)
        bar.addStretch()
        bar.addWidget(self.background_button)
        bar.addWidget(self.clear_background_button)
        bar.addWidget(self.new_button)
        root.addLayout(bar)
        self.notice = QLabel("")
        self.notice.setObjectName("ShelfMessage")
        self.notice.setWordWrap(True)
        self.notice.hide()
        root.addWidget(self.notice)

        body = QHBoxLayout()
        self.shelves_widget = QWidget()
        self.shelves_widget.setObjectName("Shelves")
        self.shelves = QVBoxLayout(self.shelves_widget)
        self.shelves.setContentsMargins(0, 0, 0, 0)
        self.shelves.setSpacing(2)
        self.rows = []
        for index in range(SHELF_COUNT):
            row = ShelfRow(index, SHELF_CAPACITY)
            row.book_dropped.connect(lambda book_id, at, shelf=index: self.move_book(book_id, shelf, at))
            self.shelves.addWidget(row)
            self.rows.append(row)
        self.shelves.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("ShelfScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.shelves_widget)
        scroll.setMinimumWidth(self.rows[0].minimumWidth() + 4)  # a full shelf always fits; no sideways scroll
        body.addWidget(scroll, 1)

        self.open_zone = DropZone(SHELF_BOOK, "Open\n\nDrag a book here\n(or double-click it)")
        self.open_zone.setObjectName("OpenZone")
        self.open_zone.setFixedWidth(220)
        self.open_zone.dropped.connect(window.open_research)
        body.addWidget(self.open_zone)
        root.addLayout(body, 1)

        self.load_background()

    # --- background --------------------------------------------------------

    def load_background(self) -> None:
        path = load_settings().get("background")
        pixmap = QPixmap(path) if path and Path(path).exists() else None
        self.background = pixmap if pixmap and not pixmap.isNull() else None
        self.clear_background_button.setVisible(self.background is not None)
        self.update()

    def choose_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose a background image", str(Path.home()),
                                              "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            self.set_background(path)

    def set_background(self, path: str | None) -> None:
        settings = load_settings()
        if path:
            config.backgrounds_dir.mkdir(parents=True, exist_ok=True)
            target = config.backgrounds_dir / Path(path).name
            if Path(path).resolve() != target.resolve():
                shutil.copyfile(path, target)
            settings["background"] = str(target)
        else:
            settings.pop("background", None)
        save_settings(settings)
        self.load_background()

    def paintEvent(self, event):
        super().paintEvent(event)  # stylesheet background
        if self.background:
            painter = QPainter(self)
            scaled = self.background.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                            Qt.TransformationMode.SmoothTransformation)
            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2
            painter.drawPixmap(0, 0, scaled, x, y, self.width(), self.height())

    # --- shelf -------------------------------------------------------------

    def refresh(self) -> None:
        for row in self.rows:
            for spine in row.spines():
                spine.deleteLater()
                row.row.removeWidget(spine)
        try:
            books = db.list_shelf_books()
        except Exception as exc:
            self._notice(f"Couldn't load your shelves: {exc}")
            return
        for book in books:
            self.rows[min(book.shelf, len(self.rows) - 1)].add_spine(self._spine(book))
        full = db.library_is_full()  # same rule create_shelf_book uses: no shelf has room
        self.new_button.setEnabled(not full)
        self.new_button.setToolTip("Your bookcase is full" if full else "")
        if full:
            self._notice(f"Your bookcase is full ({SHELF_COUNT} shelves × {SHELF_CAPACITY} books). "
                         "Delete a book to make room for new research.")
        elif not books:
            self._notice("Your shelves are empty. Press “New research” to start your first book.")
        else:
            self._notice("")

    def _notice(self, text: str) -> None:
        self.notice.setText(text)
        self.notice.setVisible(bool(text))

    def move_book(self, book_id: int, shelf: int, index: int) -> None:
        try:
            db.move_shelf_book(book_id, shelf, index)
        except db.ShelfFull:
            self._notice(f"Shelf {shelf + 1} is full. Move a book off it first.")
            return
        self.refresh()

    def _spine(self, book) -> BookSpine:
        tile = BookSpine(book.id, book.title, book.spine_color, book.spine_design)
        tile.setToolTip(f"{book.title}\n{len(book.source_ids)} source(s) · started {book.created_at:%d %b %Y}")
        tile.double_clicked.connect(self.window_.open_research)
        tile.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tile.customContextMenuRequested.connect(lambda pos, t=tile: self._book_menu(t, pos))
        return tile

    def _book_menu(self, tile: BookTile, pos) -> None:
        menu = QMenu(self)
        open_action = menu.addAction("Open")
        rename_action = menu.addAction("Rename…")
        look_action = menu.addAction("Change look…")
        delete_action = menu.addAction("Delete…")
        chosen = menu.exec(tile.mapToGlobal(pos))
        if chosen is open_action:
            self.window_.open_research(tile.item_id)
        elif chosen is rename_action:
            self.rename_book(tile)
        elif chosen is look_action:
            self.change_look(tile)
        elif chosen is delete_action:
            self.delete_book(tile)

    def rename_book(self, tile: BookTile) -> None:
        title, ok = QInputDialog.getText(self, "Rename book", "New title:", text=tile.title)
        if ok and title.strip():
            db.rename_shelf_book(tile.item_id, title.strip())
            self.refresh()

    def change_look(self, tile: BookSpine) -> None:
        dialog = SpineLookDialog(tile.title, tile.color, tile.design, self)
        if dialog.exec() == SpineLookDialog.DialogCode.Accepted:
            db.set_spine_look(tile.item_id, dialog.color, dialog.design)
            tile.set_look(dialog.color, dialog.design)

    def delete_book(self, tile: BookTile) -> None:
        answer = QMessageBox.question(
            self, "Delete book",
            f"Delete “{tile.title}” from your shelf?\n\nDownloaded textbooks and papers are kept.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            db.delete_shelf_book(tile.item_id)
            self.refresh()
