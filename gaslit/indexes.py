"""GASLIT Atlas index definitions.

Three index types live here:

1. Atlas Vector Search index `memories_vector_idx` — 1024-dim cosine, prefilters
   on (user_id, source_type, quarantined) per PRD §10.
2. Atlas Search index `memories_text_idx` — BM25 on source_text. Provenance text
   index on belief_provenance for the second arm of the hybrid retrieval.
3. Standard MongoDB indexes — compound on (memory_id, written_at), (user_id,
   written_at), (memory_id, ts) on retrieval_log; TTL on quarantine (30 d) and
   retrieval_log (7 d).

Idempotent: re-running creates only what's missing.
"""
from __future__ import annotations

import time

from pymongo.database import Database
from pymongo.operations import IndexModel, SearchIndexModel
from pymongo import ASCENDING, DESCENDING

from gaslit.schemas import (
    MEMORIES, BELIEF_PROVENANCE, RETRIEVAL_LOG, QUARANTINE, BELIEF_CONTRACTS,
    EMBEDDING_DIM, VECTOR_INDEX, TEXT_INDEX, PROVENANCE_TEXT_INDEX,
    QUARANTINE_TTL_SECONDS, RETRIEVAL_LOG_TTL_SECONDS,
)


# ─── Standard MongoDB indexes ─────────────────────────────────────────
def create_standard_indexes(db: Database) -> dict[str, list[str]]:
    """Compound indexes + TTLs. Returns {collection: [index_names]}."""
    created: dict[str, list[str]] = {}

    created[MEMORIES] = list(db[MEMORIES].create_indexes([
        IndexModel([("memory_id", ASCENDING)], unique=True, name="memory_id_unique"),
        IndexModel([("memory_id", ASCENDING), ("written_at", DESCENDING)],
                   name="memory_id_written_at"),
        IndexModel([("user_id", ASCENDING), ("written_at", DESCENDING)],
                   name="user_id_written_at"),
        IndexModel([("quarantined", ASCENDING), ("drift_score", DESCENDING)],
                   name="quarantined_drift"),
    ]))

    created[BELIEF_PROVENANCE] = list(db[BELIEF_PROVENANCE].create_indexes([
        IndexModel([("memory_id", ASCENDING)], unique=True, name="memory_id_unique"),
        IndexModel([("parent_memory_id", ASCENDING)], name="parent_for_graphlookup"),
    ]))

    created[RETRIEVAL_LOG] = list(db[RETRIEVAL_LOG].create_indexes([
        IndexModel([("memory_id", ASCENDING), ("ts", DESCENDING)],
                   name="memory_id_ts"),
        IndexModel([("ts", ASCENDING)], expireAfterSeconds=RETRIEVAL_LOG_TTL_SECONDS,
                   name="ts_ttl_7d"),
        IndexModel([("contract_id", ASCENDING), ("ts", DESCENDING)],
                   name="contract_id_ts"),
    ]))

    created[QUARANTINE] = list(db[QUARANTINE].create_indexes([
        IndexModel([("quarantine_id", ASCENDING)], unique=True, name="quarantine_id_unique"),
        IndexModel([("memory_id", ASCENDING)], name="memory_id"),
        IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0,
                   name="expires_at_ttl"),
    ]))

    created[BELIEF_CONTRACTS] = list(db[BELIEF_CONTRACTS].create_indexes([
        IndexModel([("contract_id", ASCENDING)], unique=True, name="contract_id_unique"),
        IndexModel([("tier", ASCENDING)], name="tier"),
    ]))

    return created


# ─── Atlas Vector Search index ────────────────────────────────────────
def vector_index_definition() -> dict:
    """1024-dim cosine vector search with prefilters per PRD §10."""
    return {
        "fields": [
            {
                "type": "vector",
                "path": "embedding",
                "numDimensions": EMBEDDING_DIM,
                "similarity": "cosine",
            },
            {"type": "filter", "path": "user_id"},
            {"type": "filter", "path": "source_type"},
            {"type": "filter", "path": "quarantined"},
        ]
    }


# ─── Atlas Search (BM25) index ────────────────────────────────────────
def text_index_definition() -> dict:
    """BM25 on memories.source_text — first arm of $rankFusion."""
    return {
        "mappings": {
            "dynamic": False,
            "fields": {
                "source_text": {
                    "type": "string",
                    "analyzer": "lucene.standard",
                },
                "user_id": {"type": "token"},
                "source_type": {"type": "token"},
                "quarantined": {"type": "boolean"},
            },
        }
    }


def provenance_text_index_definition() -> dict:
    """BM25 on belief_provenance — second arm of $rankFusion (per PRD §7)."""
    return {
        "mappings": {
            "dynamic": False,
            "fields": {
                "source_text_hash": {"type": "token"},
                "memory_id": {"type": "token"},
            },
        }
    }


def create_search_indexes(db: Database) -> list[str]:
    """Create Atlas Search + Vector Search indexes if missing.

    Returns names of indexes that were created (existing ones skipped).
    """
    created: list[str] = []

    memories_existing = {idx["name"] for idx in db[MEMORIES].list_search_indexes()}
    if VECTOR_INDEX not in memories_existing:
        db[MEMORIES].create_search_index(model=SearchIndexModel(
            definition=vector_index_definition(),
            name=VECTOR_INDEX,
            type="vectorSearch",
        ))
        created.append(f"{MEMORIES}.{VECTOR_INDEX}")

    if TEXT_INDEX not in memories_existing:
        db[MEMORIES].create_search_index(model=SearchIndexModel(
            definition=text_index_definition(),
            name=TEXT_INDEX,
            type="search",
        ))
        created.append(f"{MEMORIES}.{TEXT_INDEX}")

    prov_existing = {idx["name"] for idx in db[BELIEF_PROVENANCE].list_search_indexes()}
    if PROVENANCE_TEXT_INDEX not in prov_existing:
        db[BELIEF_PROVENANCE].create_search_index(model=SearchIndexModel(
            definition=provenance_text_index_definition(),
            name=PROVENANCE_TEXT_INDEX,
            type="search",
        ))
        created.append(f"{BELIEF_PROVENANCE}.{PROVENANCE_TEXT_INDEX}")

    return created


def wait_for_search_indexes(db: Database, timeout_s: int = 600) -> None:
    """Poll until vector + text indexes report status 'READY'.

    Atlas Search index builds typically take 30–90 s on M10. We block here so
    callers (setup_indexes.py) can fail loudly instead of silently moving on.
    """
    targets = [
        (MEMORIES, VECTOR_INDEX),
        (MEMORIES, TEXT_INDEX),
        (BELIEF_PROVENANCE, PROVENANCE_TEXT_INDEX),
    ]
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        ready = []
        for coll, name in targets:
            idx = next((i for i in db[coll].list_search_indexes() if i["name"] == name), None)
            if idx and idx.get("queryable"):
                ready.append((coll, name))
        if len(ready) == len(targets):
            return
        time.sleep(5)
    raise TimeoutError(
        f"Atlas Search indexes not READY after {timeout_s}s. "
        f"Check Atlas → Cluster0 → Atlas Search."
    )
