import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from locallibrary.ui.falling import Body, FallLayer, step


def _run(body: Body, dt: float = 0.01, limit: int = 1000) -> list[tuple[float, float]]:
    """Step until settled; return (y, vy) after each step."""
    trace = []
    for _ in range(limit):
        step(body, dt)
        trace.append((body.y, body.vy))
        if body.settled:
            break
    return trace


def test_falls_faster_and_faster():
    body = Body(y=-100, floor=500)
    speeds = [vy for _, vy in _run(body)[:10]]
    assert all(b > a > 0 for a, b in zip(speeds, speeds[1:]))


def test_bounces_lower_each_time_then_settles_on_the_floor():
    body = Body(y=-100, floor=500)
    trace = _run(body)
    bounce_speeds = [-vy for y, vy in trace if y == 500 and vy < 0]
    assert len(bounce_speeds) >= 2
    assert all(b < a for a, b in zip(bounce_speeds, bounce_speeds[1:]))
    assert body.settled and body.y == 500 and body.vy == 0
    assert all(y <= 500 for y, _ in trace)  # never sinks through the shelf


def test_waits_for_its_delay():
    body = Body(y=0, floor=100, delay=0.1)
    step(body, 0.05)
    assert body.y == 0 and not body.started
    step(body, 0.06)
    assert body.started and body.y > 0


def test_layer_hides_books_while_falling_and_shows_them_when_landed():
    QApplication.instance() or QApplication([])
    page = QWidget()
    page.resize(400, 600)
    books = [QWidget(page) for _ in range(3)]
    for i, book in enumerate(books):
        book.setGeometry(10 + 90 * i, 400, 76, 160)
    page.show()
    layer = FallLayer(page)
    layer.drop(books)
    assert all(not b.isVisible() for b in books) and layer.isVisible()
    for _ in range(500):
        layer.advance(0.016)
        if not layer.falling:
            break
    assert all(b.isVisible() for b in books) and not layer.isVisible()


def test_finish_lands_everything_and_offscreen_books_do_not_fall():
    QApplication.instance() or QApplication([])
    page = QWidget()
    page.resize(400, 600)
    viewport = QWidget(page)
    viewport.setGeometry(0, 0, 400, 300)
    inside, outside = QWidget(page), QWidget(page)
    inside.setGeometry(10, 100, 76, 160)
    outside.setGeometry(10, 400, 76, 160)
    page.show()
    layer = FallLayer(page)
    layer.drop([inside, outside], viewport)
    assert [w for w, _, _ in layer.falling] == [inside] and outside.isVisible()
    layer.finish()
    assert inside.isVisible() and not layer.falling
