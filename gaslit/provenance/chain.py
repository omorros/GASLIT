"""Walk the belief-provenance chain via $graphLookup.

The Forensic Auditor calls `get_chain(memory_id)` after a quarantine event to
reconstruct the lineage of a poisoned memory. PRD §4.1, §7.

`belief_provenance.parent_memory_id` is indexed (`indexes.py`), so the
$graphLookup is cheap even for long chains.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

from gaslit.schemas import BELIEF_PROVENANCE, DB_NAME

load_dotenv()

_client: Optional[MongoClient] = None


def _db() -> Database:
    """Lazy module-level client so importing this file doesn't hit the network."""
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGODB_URI"])
    return _client[DB_NAME]


def get_chain(memory_id: str, max_depth: int = 32) -> list[dict[str, Any]]:
    """Return the provenance chain for a memory, root → leaf.

    Each entry: {memory_id, source_text_hash, parent_memory_id, attestation,
    tool_output_hashes, written_at}.

    Internally uses $graphLookup starting from `memory_id`, walking
    `parent_memory_id` upward, then sorts by depth so the root comes first.
    """
    pipeline = [
        {"$match": {"memory_id": memory_id}},
        {"$graphLookup": {
            "from": BELIEF_PROVENANCE,
            "startWith": "$parent_memory_id",
            "connectFromField": "parent_memory_id",
            "connectToField": "memory_id",
            "as": "ancestors",
            "maxDepth": max_depth,
            "depthField": "depth",
        }},
    ]
    docs = list(_db()[BELIEF_PROVENANCE].aggregate(pipeline))
    if not docs:
        return []
    leaf = docs[0]
    ancestors = sorted(leaf.pop("ancestors", []), key=lambda d: -d["depth"])
    chain = [_clean(a) for a in ancestors] + [_clean(leaf)]
    return chain


def _clean(doc: dict[str, Any]) -> dict[str, Any]:
    """Strip Mongo internals (_id, depth) from a provenance doc."""
    return {k: v for k, v in doc.items() if k not in ("_id", "depth")}
