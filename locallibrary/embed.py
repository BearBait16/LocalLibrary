"""nomic-embed-text helpers. Always embed through here: the model needs task prefixes."""
import ollama

from locallibrary.config import config

DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "
BATCH_SIZE = 32


def _client() -> ollama.Client:
    return ollama.Client(host=config.ollama_host)


def document_texts(texts: list[str]) -> list[str]:
    return [DOCUMENT_PREFIX + t for t in texts]


def query_text(text: str) -> str:
    return QUERY_PREFIX + text


def _embed(inputs: list[str]) -> list[list[float]]:
    return list(_client().embed(model=config.embed_model, input=inputs).embeddings)


def embed_documents(texts: list[str], progress_callback=None) -> list[list[float]]:
    """Embed text that will be stored. `progress_callback(done, total)` is called per batch."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        vectors.extend(_embed(document_texts(texts[start:start + BATCH_SIZE])))
        if progress_callback:
            progress_callback(len(vectors), len(texts))
    return vectors


def embed_query(text: str) -> list[float]:
    """Embed a user query or question for searching."""
    return _embed([query_text(text)])[0]
