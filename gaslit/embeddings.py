"""Voyage AI embeddings — single point of contact for all embedding calls.

Lazy-init: importing this module does not require VOYAGE_API_KEY. Callers fail
loudly only when they actually try to embed.

Voyage 3 large is 1024-dim by default. PRD §7, §8.
"""
from __future__ import annotations

import os
from typing import Iterable

from dotenv import load_dotenv

load_dotenv()

VOYAGE_MODEL = os.environ.get("VOYAGE_MODEL", "voyage-3-large")
VOYAGE_DIM = int(os.environ.get("VOYAGE_DIM", "1024"))

_client = None


class EmbeddingServiceError(RuntimeError):
    """Embedding provider unavailable (quota, rate limit, outage)."""


def _embedding_rate_limited(exc: BaseException) -> bool:
    name = type(exc).__name__
    if "RateLimit" in name:
        return True
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "too many requests" in msg


def _get():
    global _client
    if _client is None:
        import voyageai
        _client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    return _client


def embed_query(text: str) -> list[float]:
    """Embed a single query string (input_type='query')."""
    try:
        out = _get().embed([text], model=VOYAGE_MODEL, input_type="query")
        return out.embeddings[0]
    except Exception as exc:
        if _embedding_rate_limited(exc):
            raise EmbeddingServiceError(
                "Voyage AI rate limit or quota exceeded — retry shortly or verify billing."
            ) from exc
        raise


def embed_documents(texts: Iterable[str], batch_size: int = 64) -> list[list[float]]:
    """Embed N documents (input_type='document'). Auto-batches to respect Voyage limits."""
    texts = list(texts)
    if not texts:
        return []
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i + batch_size]
        try:
            result = _get().embed(chunk, model=VOYAGE_MODEL, input_type="document")
        except Exception as exc:
            if _embedding_rate_limited(exc):
                raise EmbeddingServiceError(
                    "Voyage AI rate limit or quota exceeded — retry shortly or verify billing."
                ) from exc
            raise
        out.extend(result.embeddings)
    return out
