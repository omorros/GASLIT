"""Librarian agent — thin LangGraph-ready wrapper around `retrieval/librarian`.

Per PRD §5: Librarian is per-retrieval, Sonnet 4.6, "auto-classifies tool tier,
constructs adaptive hybrid retrieval, applies belief contract filter, logs
every retrieval to retrieval_log."

The implementation lives in `gaslit.retrieval.librarian`. This module re-exports
the single public function for callers that prefer to think in agent terms.
"""
from __future__ import annotations

from gaslit.retrieval.librarian import (
    retrieve as retrieve,
    retrieve_with_audit as retrieve_with_audit,
    retrieve_unprotected as retrieve_unprotected,
)

__all__ = ["retrieve", "retrieve_with_audit", "retrieve_unprotected"]
