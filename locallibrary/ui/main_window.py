"""Main window: a stack of the Library, Search and Research pages."""
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QStackedWidget

from locallibrary.ui.library_page import LibraryPage
from locallibrary.ui.research_page import ResearchPage
from locallibrary.ui.search_page import SearchPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LocalLibrary")
        self.resize(1280, 820)
        self.stack = QStackedWidget()
        self.library_page = LibraryPage(self)
        self.search_page = SearchPage(self)
        self.research_page = ResearchPage(self)
        for page in (self.library_page, self.search_page, self.research_page):
            self.stack.addWidget(page)
        self.setCentralWidget(self.stack)

        menu = self.menuBar().addMenu("&Library")
        self.refresh_action = QAction("Refresh catalog", self)
        menu.addAction(self.refresh_action)

    def _leave_current(self) -> None:
        if self.stack.currentWidget() is self.research_page:
            self.research_page.on_leave()

    def show_library(self) -> None:
        self._leave_current()
        self.library_page.refresh()
        self.stack.setCurrentWidget(self.library_page)

    def show_search(self) -> None:
        self._leave_current()
        self.search_page.reset()
        self.stack.setCurrentWidget(self.search_page)

    def open_research(self, shelf_book_id: int) -> None:
        self._leave_current()
        self.stack.setCurrentWidget(self.research_page)  # show first so the PDF view has its real size
        self.research_page.load(shelf_book_id)

    def show_status(self, message: str, timeout_ms: int = 0) -> None:
        self.statusBar().showMessage(message, timeout_ms)

    def closeEvent(self, event):
        self._leave_current()
        super().closeEvent(event)
