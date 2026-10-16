"""Postgres connection, schema setup and every SQL query in the app."""
from contextlib import contextmanager

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from locallibrary.config import EMBED_DIM, SHELF_CAPACITY, SHELF_COUNT, config
from locallibrary.looks import pick_look
from locallibrary.models import Chunk, ShelfBook, Source

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS sources (
    id serial PRIMARY KEY,
    title text NOT NULL,
    source_type text NOT NULL CHECK (source_type IN ('textbook', 'research_paper', 'web_article')),
    origin text NOT NULL CHECK (origin IN ('openstax', 'openalex', 'gemini', 'local')),
    url text NOT NULL UNIQUE,
    local_path text,
    description text NOT NULL DEFAULT '',
    summary_embedding vector({EMBED_DIM}),
    downloaded boolean NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS chunks (
    id serial PRIMARY KEY,
    source_id integer NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    page integer NOT NULL,
    text text NOT NULL,
    embedding vector({EMBED_DIM}) NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_source_idx ON chunks (source_id);

CREATE TABLE IF NOT EXISTS shelf_books (
    id serial PRIMARY KEY,
    title text NOT NULL,
    query text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_source_id integer REFERENCES sources(id) ON DELETE SET NULL,
    last_page integer NOT NULL DEFAULT 1
);

ALTER TABLE shelf_books ADD COLUMN IF NOT EXISTS spine_color integer;
ALTER TABLE shelf_books ADD COLUMN IF NOT EXISTS spine_design text;
ALTER TABLE shelf_books ADD COLUMN IF NOT EXISTS shelf integer;
ALTER TABLE shelf_books ADD COLUMN IF NOT EXISTS shelf_position integer;

CREATE TABLE IF NOT EXISTS shelf_book_sources (
    shelf_book_id integer NOT NULL REFERENCES shelf_books(id) ON DELETE CASCADE,
    source_id integer NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    position integer NOT NULL,
    PRIMARY KEY (shelf_book_id, source_id)
);
"""



class LibraryFull(Exception):
    """Every shelf is full, so no new shelf book can be placed."""


class ShelfFull(Exception):
    """The target shelf has no room for a book from another shelf."""


SOURCE_COLUMNS = "id, title, source_type, origin, url, local_path, description, downloaded"


@contextmanager
def connect():
    """Open a connection with the vector type registered; commits on success."""
    with psycopg.connect(config.database_url, row_factory=dict_row) as conn:
        register_vector(conn)
        yield conn


def init_schema() -> None:
    with psycopg.connect(config.database_url) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    with connect() as conn:
        conn.execute(SCHEMA)
        _backfill_looks(conn)
        _backfill_shelves(conn)


def _looks(conn) -> list[tuple[int, str]]:
    rows = conn.execute(
        "SELECT spine_color, spine_design FROM shelf_books WHERE spine_color IS NOT NULL ORDER BY created_at, id"
    ).fetchall()
    return [(r["spine_color"], r["spine_design"]) for r in rows]


def _backfill_looks(conn) -> None:
    """Books saved before spine looks existed get one, in creation order."""
    rows = conn.execute("SELECT id FROM shelf_books WHERE spine_color IS NULL ORDER BY created_at, id").fetchall()
    looks = _looks(conn)
    for row in rows:
        look = pick_look(looks, looks[-1] if looks else None)
        conn.execute("UPDATE shelf_books SET spine_color = %s, spine_design = %s WHERE id = %s", (*look, row["id"]))
        looks.append(look)


def _source(row: dict) -> Source:
    return Source(
        id=row["id"],
        title=row["title"],
        source_type=row["source_type"],
        origin=row["origin"],
        url=row["url"],
        local_path=row["local_path"],
        description=row["description"],
        downloaded=row["downloaded"],
    )


def _vec(embedding: list[float] | None) -> Vector | None:
    return Vector(embedding) if embedding is not None else None


# --- sources -----------------------------------------------------------------

def upsert_source(source: Source, summary_embedding: list[float] | None = None) -> Source:
    """Insert a source, or update title/description/embedding if its URL is already known.

    Download state (local_path, downloaded) is never overwritten by an upsert.
    """
    with connect() as conn:
        row = conn.execute(
            f"""
            INSERT INTO sources (title, source_type, origin, url, local_path, description,
                                 summary_embedding, downloaded)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                summary_embedding = COALESCE(EXCLUDED.summary_embedding, sources.summary_embedding)
            RETURNING {SOURCE_COLUMNS}
            """,
            (source.title, source.source_type, source.origin, source.url, source.local_path,
             source.description, _vec(summary_embedding), source.downloaded),
        ).fetchone()
    return _source(row)


def get_source(source_id: int) -> Source | None:
    with connect() as conn:
        row = conn.execute(f"SELECT {SOURCE_COLUMNS} FROM sources WHERE id = %s", (source_id,)).fetchone()
    return _source(row) if row else None


def get_source_by_url(url: str) -> Source | None:
    with connect() as conn:
        row = conn.execute(f"SELECT {SOURCE_COLUMNS} FROM sources WHERE url = %s", (url,)).fetchone()
    return _source(row) if row else None


def get_sources(source_ids: list[int]) -> list[Source]:
    """Return sources in the same order as `source_ids`."""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT {SOURCE_COLUMNS} FROM sources WHERE id = ANY(%s)", (source_ids,)
        ).fetchall()
    by_id = {row["id"]: _source(row) for row in rows}
    return [by_id[i] for i in source_ids if i in by_id]


def count_sources(source_type: str | None = None) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT count(*) AS n FROM sources WHERE %s::text IS NULL OR source_type = %s",
            (source_type, source_type),
        ).fetchone()
    return row["n"]


def mark_downloaded(source_id: int, local_path: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE sources SET local_path = %s, downloaded = true WHERE id = %s",
            (local_path, source_id),
        )


def set_summary_embedding(source_id: int, embedding: list[float]) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE sources SET summary_embedding = %s WHERE id = %s", (_vec(embedding), source_id)
        )


def get_summary_embedding(source_id: int) -> list[float] | None:
    with connect() as conn:
        row = conn.execute("SELECT summary_embedding FROM sources WHERE id = %s", (source_id,)).fetchone()
    return row["summary_embedding"].to_list() if row and row["summary_embedding"] is not None else None


def search_sources(
    embedding: list[float],
    source_type: str | None = None,
    limit: int = 10,
    exclude_ids: list[int] | None = None,
) -> list[tuple[Source, float]]:
    """Nearest sources by summary embedding. Returns (source, cosine distance) pairs."""
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT {SOURCE_COLUMNS}, summary_embedding <=> %(e)s AS distance
            FROM sources
            WHERE summary_embedding IS NOT NULL
              AND (%(t)s::text IS NULL OR source_type = %(t)s)
              AND NOT (id = ANY(%(x)s))
            ORDER BY distance
            LIMIT %(n)s
            """,
            {"e": _vec(embedding), "t": source_type, "x": exclude_ids or [], "n": limit},
        ).fetchall()
    return [(_source(row), row["distance"]) for row in rows]


# --- chunks ------------------------------------------------------------------

def replace_chunks(source_id: int, chunks: list[tuple[int, str, list[float]]]) -> None:
    """Delete a source's chunks and store new (page, text, embedding) rows in one transaction."""
    with connect() as conn:
        conn.execute("DELETE FROM chunks WHERE source_id = %s", (source_id,))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (source_id, page, text, embedding) VALUES (%s, %s, %s, %s)",
                [(source_id, page, text, _vec(emb)) for page, text, emb in chunks],
            )


def count_chunks(source_id: int) -> int:
    with connect() as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM chunks WHERE source_id = %s", (source_id,)
        ).fetchone()["n"]


def search_chunks(
    embedding: list[float], source_ids: list[int] | None = None, limit: int = 6
) -> list[Chunk]:
    """Nearest chunks by cosine distance, optionally limited to some sources."""
    with connect() as conn:
        # Filtered HNSW scans can return too few rows; iterative scans keep searching.
        conn.execute("SET hnsw.iterative_scan = relaxed_order")
        rows = conn.execute(
            """
            SELECT id, source_id, page, text, embedding <=> %(e)s AS distance
            FROM chunks
            WHERE %(ids)s::int[] IS NULL OR source_id = ANY(%(ids)s)
            ORDER BY distance
            LIMIT %(n)s
            """,
            {"e": _vec(embedding), "ids": source_ids, "n": limit},
        ).fetchall()
    return [
        Chunk(id=r["id"], source_id=r["source_id"], page=r["page"], text=r["text"], distance=r["distance"])
        for r in rows
    ]


# --- shelf books -------------------------------------------------------------

def _shelf_ids(conn, shelf: int) -> list[int]:
    rows = conn.execute(
        "SELECT id FROM shelf_books WHERE shelf = %s ORDER BY shelf_position, id", (shelf,)
    ).fetchall()
    return [r["id"] for r in rows]


def _write_shelf(conn, shelf: int, ids: list[int]) -> None:
    """Store `ids` as the books on `shelf`, left to right, with positions 0..n-1."""
    for position, book_id in enumerate(ids):
        conn.execute(
            "UPDATE shelf_books SET shelf = %s, shelf_position = %s WHERE id = %s", (shelf, position, book_id)
        )


def _free_shelf(conn) -> int | None:
    """The first shelf with room, or None when the bookcase is full."""
    for shelf in range(SHELF_COUNT):
        if len(_shelf_ids(conn, shelf)) < SHELF_CAPACITY:
            return shelf
    return None


def _backfill_shelves(conn) -> None:
    """Books saved before shelves existed are placed in creation order, filling shelf 1 first.

    If there are more such books than free spots, the extras go on the last shelf so none disappear.
    """
    rows = conn.execute("SELECT id FROM shelf_books WHERE shelf IS NULL ORDER BY created_at, id").fetchall()
    for row in rows:
        shelf = _free_shelf(conn)
        shelf = SHELF_COUNT - 1 if shelf is None else shelf
        _write_shelf(conn, shelf, _shelf_ids(conn, shelf) + [row["id"]])


def library_is_full() -> bool:
    with connect() as conn:
        return _free_shelf(conn) is None


def move_shelf_book(shelf_book_id: int, shelf: int, index: int) -> None:
    """Put a book at `index` on `shelf` (index counts the other books on that shelf).

    Reorders within a shelf, or moves between shelves. Raises ShelfFull if another shelf has no room.
    """
    if not 0 <= shelf < SHELF_COUNT:
        raise ValueError(f"No shelf {shelf}")
    with connect() as conn:
        row = conn.execute("SELECT shelf FROM shelf_books WHERE id = %s", (shelf_book_id,)).fetchone()
        if row is None:
            return
        old_shelf = row["shelf"]
        target = [i for i in _shelf_ids(conn, shelf) if i != shelf_book_id]
        if old_shelf != shelf and len(target) >= SHELF_CAPACITY:
            raise ShelfFull(f"Shelf {shelf + 1} is full")
        target.insert(max(0, min(index, len(target))), shelf_book_id)
        _write_shelf(conn, shelf, target)
        if old_shelf is not None and old_shelf != shelf:
            _write_shelf(conn, old_shelf, _shelf_ids(conn, old_shelf))  # close the gap


def _shelf_book(row: dict, source_ids: list[int]) -> ShelfBook:
    return ShelfBook(
        id=row["id"],
        title=row["title"],
        query=row["query"],
        created_at=row["created_at"],
        last_source_id=row["last_source_id"],
        last_page=row["last_page"],
        source_ids=source_ids,
        spine_color=row["spine_color"] if row["spine_color"] is not None else 0,
        spine_design=row["spine_design"] or "bands",
        shelf=row["shelf"] or 0,
        shelf_position=row["shelf_position"] or 0,
    )


def create_shelf_book(title: str, query: str, source_ids: list[int], last_source_id: int | None) -> ShelfBook:
    """Save a new shelf book at the end of the first shelf with room. Raises LibraryFull."""
    with connect() as conn:
        shelf = _free_shelf(conn)
        if shelf is None:
            raise LibraryFull("Every shelf is full")
        on_shelf = _shelf_ids(conn, shelf)
        neighbor = conn.execute(
            "SELECT spine_color, spine_design FROM shelf_books WHERE id = %s", (on_shelf[-1],)
        ).fetchone() if on_shelf else None
        color, design = pick_look(_looks(conn), (neighbor["spine_color"], neighbor["spine_design"]) if neighbor else None)
        row = conn.execute(
            """INSERT INTO shelf_books (title, query, last_source_id, spine_color, spine_design, shelf, shelf_position)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (title, query, last_source_id, color, design, shelf, len(on_shelf)),
        ).fetchone()
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO shelf_book_sources (shelf_book_id, source_id, position) VALUES (%s, %s, %s)",
                [(row["id"], sid, pos) for pos, sid in enumerate(source_ids)],
            )
    return _shelf_book(row, list(source_ids))


def _source_ids(conn, shelf_book_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT source_id FROM shelf_book_sources WHERE shelf_book_id = %s ORDER BY position",
        (shelf_book_id,),
    ).fetchall()
    return [r["source_id"] for r in rows]


def get_shelf_book(shelf_book_id: int) -> ShelfBook | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM shelf_books WHERE id = %s", (shelf_book_id,)).fetchone()
        return _shelf_book(row, _source_ids(conn, shelf_book_id)) if row else None


def list_shelf_books() -> list[ShelfBook]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM shelf_books ORDER BY shelf, shelf_position, id").fetchall()
        return [_shelf_book(row, _source_ids(conn, row["id"])) for row in rows]


def rename_shelf_book(shelf_book_id: int, title: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE shelf_books SET title = %s WHERE id = %s", (title, shelf_book_id))


def set_spine_look(shelf_book_id: int, color: int, design: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE shelf_books SET spine_color = %s, spine_design = %s WHERE id = %s",
            (color, design, shelf_book_id),
        )


def delete_shelf_book(shelf_book_id: int) -> None:
    with connect() as conn:
        row = conn.execute("DELETE FROM shelf_books WHERE id = %s RETURNING shelf", (shelf_book_id,)).fetchone()
        if row and row["shelf"] is not None:
            _write_shelf(conn, row["shelf"], _shelf_ids(conn, row["shelf"]))  # close the gap


def save_position(shelf_book_id: int, source_id: int, page: int) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE shelf_books SET last_source_id = %s, last_page = %s WHERE id = %s",
            (source_id, page, shelf_book_id),
        )


def add_source_to_shelf_book(shelf_book_id: int, source_id: int) -> None:
    """Append a source to the end of a shelf book (no-op if already present)."""
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO shelf_book_sources (shelf_book_id, source_id, position)
            SELECT %(b)s, %(s)s, COALESCE(max(position) + 1, 0)
            FROM shelf_book_sources WHERE shelf_book_id = %(b)s
            ON CONFLICT DO NOTHING
            """,
            {"b": shelf_book_id, "s": source_id},
        )
