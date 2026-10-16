"""Download -> extract -> chunk -> embed -> store.

CLI: python -m locallibrary.ingest <path-or-url> [--type textbook|research_paper|web_article] [--title T]
"""
import argparse
import re
import shutil
from pathlib import Path

import httpx
import pymupdf
import trafilatura

from locallibrary import db, embed
from locallibrary.config import config
from locallibrary.models import RESEARCH_PAPER, TEXTBOOK, WEB_ARTICLE, Source

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
SECTION_SIZE = 2000
# Some open-access hosts refuse requests whose user agent doesn't look like a browser.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) LocalLibrary/0.1 (desktop research app)"
MIN_TEXT_CHARS = 500  # less than this is usually a login, paywall or captcha page


def _folder(source: Source) -> Path:
    folder = config.books_dir if source.source_type == TEXTBOOK else config.resources_dir
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _filename(source: Source, suffix: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "-", source.title).strip("-")[:80] or "source"
    return f"{source.id}-{stem}{suffix}"


def is_pdf(path: Path) -> bool:
    with open(path, "rb") as f:
        return f.read(5) == b"%PDF-"


def download(source: Source, progress_callback=None) -> Source:
    """Save the source's file into data/books or data/resources and record local_path."""
    url = source.url
    if url.startswith("file://") or Path(url).exists():
        src = Path(url.removeprefix("file://"))
        target = _folder(source) / _filename(source, src.suffix or ".pdf")
        if src.resolve() != target.resolve():
            shutil.copyfile(src, target)
    else:
        part = _folder(source) / _filename(source, ".part")
        headers = {"User-Agent": USER_AGENT, "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8"}
        with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=60) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length") or 0)
            done = 0
            with open(part, "wb") as f:
                for block in resp.iter_bytes(65536):
                    f.write(block)
                    done += len(block)
                    if progress_callback and total:
                        progress_callback(done, total)
        suffix = ".pdf" if is_pdf(part) else ".html"
        target = part.with_suffix(suffix)
        part.replace(target)
    source.local_path = str(target)
    return source


def _split(text: str, size: int) -> list[str]:
    """Split text into pieces of about `size` chars, preferring paragraph breaks."""
    pieces, current = [], ""
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > size:
            pieces.append(current)
            current = ""
        current = f"{current}\n\n{para}" if current else para
    if current:
        pieces.append(current)
    return pieces


def extract(source: Source) -> list[tuple[int, str]]:
    """Return [(page, text)]. PDF pages are 1-based; web articles are numbered sections."""
    path = Path(source.local_path)
    if is_pdf(path):
        with pymupdf.open(path) as doc:
            pages = [(i + 1, page.get_text()) for i, page in enumerate(doc)]
    else:
        html = path.read_text(errors="replace")
        text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
        pages = list(enumerate(_split(text, SECTION_SIZE), start=1))
    return [(page, text.strip()) for page, text in pages if text.strip()]


def chunk(pages: list[tuple[int, str]], size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[tuple[int, str]]:
    """~`size`-char chunks with `overlap` chars shared, never crossing a page boundary."""
    chunks = []
    step = size - overlap
    for page, text in pages:
        text = re.sub(r"\s+", " ", text).strip()
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                # End on a word boundary when one is reasonably close.
                space = text.rfind(" ", start + step, end)
                if space != -1:
                    end = space
            chunks.append((page, text[start:end].strip()))
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
            # Start the next chunk on a word boundary too.
            space = text.find(" ", start, end)
            if space != -1:
                start = space + 1
    return [(p, t) for p, t in chunks if t]


def summary_text(source: Source) -> str:
    return f"{source.title}\n\n{source.description}".strip()


def ingest(source: Source, progress_callback=None) -> Source:
    """Download (if needed), extract, chunk, embed and store a source.

    `progress_callback(percent, message)` reports progress for the UI.
    """
    def report(percent: int, message: str) -> None:
        if progress_callback:
            progress_callback(percent, message)

    if source.id is None:
        source = db.upsert_source(source)

    if not source.local_path or not Path(source.local_path).exists():
        report(0, "Downloading")
        download(source, lambda done, total: report(int(30 * done / total), "Downloading"))

    report(30, "Extracting text")
    pages = extract(source)
    if sum(len(text) for _, text in pages) < MIN_TEXT_CHARS:
        raise ValueError("The download had no readable text (the site may need a login or block downloads).")
    chunks = chunk(pages)

    report(35, f"Embedding {len(chunks)} passages")
    vectors = embed.embed_documents(
        [text for _, text in chunks],
        lambda done, total: report(35 + int(60 * done / total), f"Embedding {done}/{total}"),
    )
    db.replace_chunks(source.id, [(page, text, vec) for (page, text), vec in zip(chunks, vectors)])
    db.set_summary_embedding(source.id, embed.embed_documents([summary_text(source)])[0])
    db.mark_downloaded(source.id, source.local_path)
    source.downloaded = True
    report(100, "Ready")
    return source


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest one source into the library.")
    parser.add_argument("location", help="local file path or URL")
    parser.add_argument("--type", choices=[TEXTBOOK, RESEARCH_PAPER, WEB_ARTICLE], default=TEXTBOOK)
    parser.add_argument("--title", help="title (defaults to the file name)")
    args = parser.parse_args()

    db.init_schema()
    location = args.location
    if Path(location).exists():
        location = str(Path(location).resolve())
    source = db.get_source_by_url(location) or Source(
        title=args.title or Path(location).stem,
        source_type=args.type,
        origin="local",
        url=location,
    )
    source = ingest(source, lambda pct, msg: print(f"\r{pct:3d}% {msg:<40}", end="", flush=True))
    print(f"\nIngested #{source.id} {source.title!r}: {db.count_chunks(source.id)} chunks -> {source.local_path}")


if __name__ == "__main__":
    main()
