"""Cover thumbnails for downloaded PDF sources, rendered once and cached in data/thumbnails/."""
from pathlib import Path

import pymupdf

from locallibrary.config import config
from locallibrary.ingest import is_pdf
from locallibrary.models import Source

COVER_HEIGHT = 240  # px; tiles scale it down, the Now-reading bar uses it smaller still


def cover_path(source: Source) -> Path | None:
    """Path to a PNG of the source's first page, rendering it if needed. None if there's no PDF."""
    if not source.local_path or source.id is None:
        return None
    pdf = Path(source.local_path)
    if not pdf.exists() or not is_pdf(pdf):
        return None
    target = config.thumbnails_dir / f"{source.id}.png"
    if target.exists() and target.stat().st_mtime >= pdf.stat().st_mtime:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(pdf) as doc:
        if doc.page_count == 0:
            return None
        page = doc[0]
        zoom = COVER_HEIGHT / page.rect.height
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        tmp = target.with_suffix(".tmp.png")
        pixmap.save(tmp)
        tmp.replace(target)  # never leave a half-written cover behind
    return target


def cover_paths(sources: list[Source]) -> dict[int, str]:
    """{source id: cover path} for the sources that have one. Runs in a Worker."""
    covers = {}
    for source in sources:
        path = cover_path(source)
        if path:
            covers[source.id] = str(path)
    return covers
