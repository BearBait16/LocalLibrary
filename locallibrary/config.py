"""Settings loaded from .env. Import `config` everywhere instead of reading os.environ."""
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Config:
    database_url: str
    ollama_host: str
    gemma_model: str
    gemma_num_ctx: int
    embed_model: str
    gemini_api_key: str
    gemini_model: str
    openalex_email: str
    openalex_api_key: str
    data_dir: Path

    @property
    def books_dir(self) -> Path:
        return self.data_dir / "books"

    @property
    def resources_dir(self) -> Path:
        return self.data_dir / "resources"

    @property
    def thumbnails_dir(self) -> Path:
        return self.data_dir / "thumbnails"

    @property
    def backgrounds_dir(self) -> Path:
        return self.data_dir / "backgrounds"

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)


def _data_dir() -> Path:
    path = Path(os.getenv("DATA_DIR", "./data"))
    return path if path.is_absolute() else PROJECT_ROOT / path


config = Config(
    database_url=os.getenv("DATABASE_URL", "postgresql://locallibrary:locallibrary@localhost:5432/locallibrary"),
    ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
    gemma_model=os.getenv("GEMMA_MODEL", ""),
    gemma_num_ctx=int(os.getenv("GEMMA_NUM_CTX", "8192")),
    embed_model=os.getenv("EMBED_MODEL", "nomic-embed-text"),
    gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
    gemini_model=os.getenv("GEMINI_MODEL", ""),
    openalex_email=os.getenv("OPENALEX_EMAIL", ""),
    openalex_api_key=os.getenv("OPENALEX_API_KEY", ""),
    data_dir=_data_dir(),
)

EMBED_DIM = 768

# The library bookcase: a fixed number of shelves, each holding a fixed number of books (no wrap or scroll).
SHELF_COUNT = 4
SHELF_CAPACITY = 10


def settings_path() -> Path:
    return config.data_dir / "settings.json"


def load_settings() -> dict:
    """User preferences saved by the app (e.g. the library background). {} if missing or unreadable."""
    try:
        data = json.loads(settings_path().read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict) -> None:
    settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(json.dumps(settings, indent=2))
