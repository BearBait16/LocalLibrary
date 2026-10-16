"""Run slow work (network, models, downloads, embedding) off the UI thread."""
import inspect
import traceback

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

_active: set["Worker"] = set()  # keep workers (and their signals) alive until they finish


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(int, str)


class Worker(QRunnable):
    """Calls fn(*args, **kwargs) on the thread pool.

    If fn accepts a `progress_callback` argument, it gets one that emits `progress(int, str)`.
    """

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.setAutoDelete(False)
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = WorkerSignals()
        if "progress_callback" in inspect.signature(fn).parameters:
            self.kwargs["progress_callback"] = lambda value, message="": self.signals.progress.emit(int(value), str(message))

    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # report every failure to the UI instead of crashing
            traceback.print_exc()
            self.signals.failed.emit(friendly_error(exc))
        else:
            self.signals.finished.emit(result)
        finally:
            _active.discard(self)


def friendly_error(exc: Exception) -> str:
    name = type(exc).__name__
    text = str(exc)
    if name in ("ConnectError", "ConnectionError") and ("11434" in text or "ollama" in text.lower()):
        return "Can't reach Ollama. Is `ollama serve` running?"
    if name == "OperationalError" and "connection" in text.lower():
        return "Can't reach the database. Is `docker compose up -d` running?"
    if name in ("ConnectError", "ConnectTimeout", "ReadTimeout"):
        return f"Network problem: {text or name}"
    if name == "HTTPStatusError":
        return f"Download failed: {text.splitlines()[0]}"
    return f"{name}: {text}" if text else name


def run_in_background(fn, *args, on_done=None, on_error=None, on_progress=None, **kwargs) -> Worker:
    worker = Worker(fn, *args, **kwargs)
    if on_done:
        worker.signals.finished.connect(on_done)
    if on_error:
        worker.signals.failed.connect(on_error)
    if on_progress:
        worker.signals.progress.connect(on_progress)
    _active.add(worker)
    QThreadPool.globalInstance().start(worker)
    return worker
