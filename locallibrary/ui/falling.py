"""Falling books: a small gravity-and-bounce simulation, and an overlay that drops widgets onto their places."""
from dataclasses import dataclass

from PySide6.QtCore import QElapsedTimer, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget

GRAVITY = 3200.0  # px/s²
BOUNCE = 0.35  # share of its speed a book keeps when it hits the shelf
REST_SPEED = 90.0  # px/s; a bounce slower than this and the book stays put
STAGGER = 0.09  # s between one book starting to fall and the next
MAX_STEP = 0.05  # s; a long frame (a busy UI thread) doesn't teleport books through the shelf
FRAME_MS = 16


@dataclass
class Body:
    y: float  # top edge, px
    floor: float  # y where the book rests on its shelf
    vy: float = 0.0  # px/s, positive is down
    delay: float = 0.0  # s left before it starts falling
    settled: bool = False

    @property
    def started(self) -> bool:
        return self.delay <= 0


def step(body: Body, dt: float) -> None:
    """Advance one body by dt seconds: wait out its delay, fall, bounce off the floor, settle."""
    if body.settled:
        body.y = body.floor
        return
    if body.delay > 0:
        body.delay -= dt
        if body.delay > 0:
            return
        dt, body.delay = -body.delay, 0.0
    body.vy += GRAVITY * dt
    body.y += body.vy * dt
    if body.y >= body.floor:
        body.y = body.floor
        body.vy = -body.vy * BOUNCE
        if abs(body.vy) < REST_SPEED:
            body.vy, body.settled = 0.0, True


class FallLayer(QWidget):
    """A see-through overlay covering its parent. drop() hides widgets and paints pictures of them falling from
    the top of the parent; each widget reappears when its picture lands. Clicks pass straight through."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("FallLayer")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.falling: list[tuple[QWidget, QPixmap, Body]] = []
        self.clock = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setInterval(FRAME_MS)
        self.timer.timeout.connect(self._tick)
        self.hide()

    def _target(self, widget: QWidget) -> QPoint:
        """The widget's top-left corner in layer coordinates, read every frame so scrolling is followed."""
        return widget.mapTo(self.parentWidget(), QPoint(0, 0))

    def drop(self, widgets: list[QWidget], viewport: QWidget | None = None) -> None:
        """Drop each widget into place, one after another. Widgets outside `viewport` just stay where they are."""
        visible = QRect(viewport.mapTo(self.parentWidget(), QPoint(0, 0)), viewport.size()) if viewport else None
        waiting = sum(1 for _, _, body in self.falling if not body.started)
        for widget in widgets:
            target = self._target(widget)
            if visible is not None and not visible.intersects(QRect(target, widget.size())):
                continue
            pixmap = widget.grab()
            widget.hide()
            body = Body(y=-widget.height(), floor=target.y(), delay=STAGGER * waiting)
            self.falling.append((widget, pixmap, body))
            waiting += 1
        if self.falling and not self.timer.isActive():
            self.setGeometry(self.parentWidget().rect())
            self.show()
            self.raise_()
            self.clock.start()
            self.timer.start()

    def finish(self) -> None:
        """Land every book now (a new search, or leaving the page)."""
        for widget, _, _ in self.falling:
            widget.show()
        self.falling.clear()
        self.timer.stop()
        self.hide()

    def _tick(self) -> None:
        self.advance(self.clock.restart() / 1000)

    def advance(self, dt: float) -> None:
        dt = min(dt, MAX_STEP)
        still = []
        for widget, pixmap, body in self.falling:
            body.floor = self._target(widget).y()
            step(body, dt)
            if body.settled:
                widget.show()
            else:
                still.append((widget, pixmap, body))
        self.falling = still
        if not self.falling:
            self.finish()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        for widget, pixmap, body in self.falling:
            if body.started:
                painter.drawPixmap(self._target(widget).x(), round(body.y), pixmap)
