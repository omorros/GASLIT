"""Voyage AI embeddings — single point of contact for all embedding calls.

Lazy-init: importing this module does not require VOYAGE_API_KEY. Callers fail
loudly only when they actually try to embed.

Voyage 3 large is 1024-dim by default. PRD §7, §8.
"""
from __future__ import annotations

import os
from typing import Iterable, Literal

from dotenv import load_dotenv

load_dotenv()

VOYAGE_MODEL = os.environ.get("VOYAGE_MODEL", "voyage-3-large")
VOYAGE_DIM = int(os.environ.get("VOYAGE_DIM", "1024"))

_client = None


def _get():
    global _client
    if _client is None:
        import voyageai
        _client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    return _client


def embed_query(text: str) -> list[float]:
    """Embed a single query string (input_type='query')."""
    out = _get().embed([text], model=VOYAGE_MODEL, input_type="query")
    return out.embeddings[0]


def embed_documents(texts: Iterable[str], batch_size: int = 64) -> list[list[float]]:
    """Embed N documents (input_type='document'). Auto-batches to respect Voyage limits."""
    texts = list(texts)
    if not texts:
        return []
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i + batch_size]
        result = _get().embed(chunk, model=VOYAGE_MODEL, input_type="document")
        out.extend(result.embeddings)
    return out
