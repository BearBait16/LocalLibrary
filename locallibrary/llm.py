"""Gemma (via Ollama) calls: picking sources from the local library and answering questions."""
import json

import ollama

from locallibrary.config import config
from locallibrary.models import Chunk, Source

PICK_SCHEMA = {
    "type": "object",
    "properties": {
        "textbook_id": {"type": "integer"},
        "textbook_reason": {"type": "string"},
        "papers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "reason": {"type": "string"}},
                "required": ["id", "reason"],
            },
        },
    },
    "required": ["textbook_id", "textbook_reason", "papers"],
}

PICK_PROMPT = """A student wants to learn about: "{query}"

Choose the single best TEXTBOOK to start with, and the 3 to 6 PAPERS most closely related to the topic.
Skip papers that are course syllabi, book reviews or off-topic. Only use IDs from the lists below.
Give each choice a one-line reason written for the student.

TEXTBOOKS:
{textbooks}

PAPERS:
{papers}"""

ANSWER_SYSTEM = """You are a research assistant helping a student read their sources.
Answer using ONLY the numbered passages provided. Be brief (a short paragraph or a few bullets).
Cite passages with their numbers in square brackets, like [2], and point the reader to where to look
(source title and page). If the passages don't contain the answer, say so plainly."""


def _client() -> ollama.Client:
    return ollama.Client(host=config.ollama_host)


def _options() -> dict:
    return {"temperature": 0.2, "num_ctx": config.gemma_num_ctx}


def _describe(source: Source, max_chars: int = 400) -> str:
    desc = (source.description or "").replace("\n", " ")
    if len(desc) > max_chars:
        desc = desc[:max_chars].rsplit(" ", 1)[0] + "…"
    return f"[{source.id}] {source.title}" + (f" — {desc}" if desc else "")


def pick_sources(query: str, textbooks: list[Source], papers: list[Source]) -> dict:
    """Ask Gemma to choose; returns the raw parsed JSON (the caller validates the IDs)."""
    prompt = PICK_PROMPT.format(
        query=query,
        textbooks="\n".join(_describe(s) for s in textbooks) or "(none)",
        papers="\n".join(_describe(s, 300) for s in papers) or "(none)",
    )
    response = _client().chat(
        model=config.gemma_model,
        messages=[{"role": "user", "content": prompt}],
        format=PICK_SCHEMA,
        options=_options(),
    )
    return json.loads(response.message.content)


def answer(question: str, chunks: list[Chunk], titles: dict[int, str]) -> str:
    """Answer from passages; passage n in the prompt is chunks[n-1]."""
    passages = "\n\n".join(
        f"[{n}] {titles.get(c.source_id, 'Source')}, page {c.page}:\n{c.text}"
        for n, c in enumerate(chunks, start=1)
    )
    response = _client().chat(
        model=config.gemma_model,
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM},
            {"role": "user", "content": f"PASSAGES:\n\n{passages}\n\nQUESTION: {question}"},
        ],
        options=_options(),
    )
    return response.message.content.strip()
