"""Shared local FastAPI origin for in-process adversary/demo drivers."""

from __future__ import annotations

import os

DEFAULT_API_PORT = "8002"


def local_api_base() -> str:
    """Return the local FastAPI origin used by background demo workers."""
    return f"http://127.0.0.1:{os.environ.get('API_PORT', DEFAULT_API_PORT)}"
