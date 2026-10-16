"""Plain dataclasses shared by every module."""
from dataclasses import dataclass, field
from datetime import datetime

TEXTBOOK = "textbook"
RESEARCH_PAPER = "research_paper"
WEB_ARTICLE = "web_article"


@dataclass
class Source:
    title: str
    source_type: str
    origin: str
    url: str
    description: str = ""
    local_path: str | None = None
    downloaded: bool = False
    id: int | None = None


@dataclass
class Chunk:
    source_id: int
    page: int
    text: str
    id: int | None = None
    distance: float | None = None  # set by vector searches


@dataclass
class ShelfBook:
    title: str
    query: str
    id: int | None = None
    created_at: datetime | None = None
    last_source_id: int | None = None
    last_page: int = 1
    source_ids: list[int] = field(default_factory=list)
    spine_color: int = 0  # index into looks.SPINE_COLORS
    spine_design: str = "bands"  # one of looks.SPINE_DESIGNS
    shelf: int = 0  # 0-based shelf in the bookcase
    shelf_position: int = 0  # 0-based place on that shelf, left to right
