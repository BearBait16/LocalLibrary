"""Start the LocalLibrary desktop app: python -m locallibrary.main"""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from locallibrary import db
from locallibrary.models import TEXTBOOK
from locallibrary.sources import openstax
from locallibrary.ui.main_window import MainWindow
from locallibrary.workers import run_in_background

STYLE_FILE = Path(__file__).parent / "ui" / "style.qss"


def prepare_library(progress_callback=None) -> int | None:
    """Create the schema; on first launch, sync the OpenStax catalog. Returns books synced, or None."""
    db.init_schema()
    if db.count_sources(TEXTBOOK) == 0:
        return openstax.sync_catalog(lambda done, total: progress_callback(done, f"Embedding catalog {done}/{total}"))
    return None


def refresh_catalog(window: MainWindow) -> None:
    window.show_status("Refreshing OpenStax catalog…")
    window.refresh_action.setEnabled(False)

    def done(count):
        window.refresh_action.setEnabled(True)
        window.show_status(f"Catalog refreshed: {count} textbooks.", 8000)

    def failed(message):
        window.refresh_action.setEnabled(True)
        window.show_status(f"Catalog refresh failed: {message}")

    run_in_background(openstax.sync_catalog, on_done=done, on_error=failed)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("LocalLibrary")
    app.setStyleSheet(STYLE_FILE.read_text())
    window = MainWindow()
    window.refresh_action.triggered.connect(lambda: refresh_catalog(window))
    window.show()

    def ready(count):
        window.show_status(f"Library ready. Synced {count} textbooks." if count else "Library ready.", 8000)
        window.show_library()

    window.show_status("Preparing library…")
    run_in_background(
        prepare_library,
        on_done=ready,
        on_error=lambda message: window.show_status(f"Startup problem: {message}"),
        on_progress=lambda _, message: window.show_status(message),
    )
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
