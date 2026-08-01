"""Walk the belief-provenance chain via signed parent links.

The Forensic Auditor calls `get_chain(memory_id)` after a quarantine event to
reconstruct the lineage of a poisoned memory. PRD §4.1, §7.

Parent links used for the walk come from ``memories.parent_memory_id`` — the
field included in the HMAC attestation — not the mutable copy on
``belief_provenance`` alone. Otherwise an in-place edit to
``belief_provenance.parent_memory_id`` can fabricate forensic lineage while the
leaf attestation still verifies.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

from gaslit.schemas import BELIEF_PROVENANCE, MEMORIES, DB_NAME

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

    Walks HMAC-bound ``memories.parent_memory_id`` upward, hydrating each hop
    from ``belief_provenance``. When the two parent fields diverge, the signed
    memory parent wins and the forged provenance edge is not followed.
    """
    db = _db()
    leaf_to_root: list[dict[str, Any]] = []
    current_id: Optional[str] = memory_id
    seen: set[str] = set()

    for _ in range(max_depth + 1):
        if not current_id or current_id in seen:
            break
        seen.add(current_id)

        prov = db[BELIEF_PROVENANCE].find_one({"memory_id": current_id})
        if not prov:
            break

        mem = db[MEMORIES].find_one(
            {"memory_id": current_id},
            {"_id": 0, "parent_memory_id": 1},
        )
        if mem is not None:
            parent = mem.get("parent_memory_id")
            if prov.get("parent_memory_id") != parent:
                prov = {**prov, "parent_memory_id": parent}
        else:
            # Memory row missing — cannot trust a provenance-only parent edge.
            parent = None
            if prov.get("parent_memory_id") is not None:
                prov = {**prov, "parent_memory_id": None}

        leaf_to_root.append(_clean(prov))
        current_id = parent

    return list(reversed(leaf_to_root))


def _clean(doc: dict[str, Any]) -> dict[str, Any]:
    """Strip Mongo internals (_id, depth) from a provenance doc."""
    return {k: v for k, v in doc.items() if k not in ("_id", "depth")}
