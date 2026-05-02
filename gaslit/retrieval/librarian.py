"""Adaptive retrieval entry point — `retrieve()` is the only public function the
Librarian agent calls.

Flow:
1. Look up the belief contract for tool_context["tool_name"].
2. Embed the query via Voyage.
3. Run hybrid retrieval with the contract's rank_weights.
4. Apply contract filters (quarantined / drift / source_type).
5. For high_stakes contracts, verify HMAC attestation.
6. Log every retrieval (passed AND filtered) to retrieval_log so the Sentinel
   sees the full picture for cohort-variance computation.
7. Return the memories that passed.

Two public functions:

- `retrieve(query_text, tool_context) -> list[memory]`
    Used by the Librarian agent on the protected path.

- `retrieve_with_audit(query_text, tool_context) -> {memories, filtered, contract}`
    Used by `/api/gaslit-agent` so the frontend can show what was filtered out
    and why. Same internal logic.

- `retrieve_unprotected(query_text, tool_context) -> list[memory]`
    Used by `/api/unprotected-agent`. Same hybrid retrieval, NO contract filter,
    NO HMAC verification. Same retrieval is logged so drift detection works
    on the unprotected path's traffic too.

PRD §4.3, §5.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

from gaslit.embeddings import embed_query
from gaslit.provenance.hmac import verify, signing_fields
from gaslit.retrieval.contracts import get_contract
from gaslit.retrieval.hybrid import hybrid_retrieve
from gaslit.schemas import BELIEF_PROVENANCE, RETRIEVAL_LOG, DB_NAME

load_dotenv()

_client: Optional[MongoClient] = None


def _db() -> Database:
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGODB_URI"])
    return _client[DB_NAME]


# ─── Filter evaluation ────────────────────────────────────────────────
_OPS = {
    "$lt":  lambda v, t: v is not None and v <  t,
    "$lte": lambda v, t: v is not None and v <= t,
    "$gt":  lambda v, t: v is not None and v >  t,
    "$gte": lambda v, t: v is not None and v >= t,
    "$ne":  lambda v, t: v != t,
    "$eq":  lambda v, t: v == t,
}


def _passes_filters(memory: dict, filters: list[dict]) -> bool:
    """Lightweight Mongo-style filter eval over a single document."""
    for f in filters:
        for k, condition in f.items():
            v = memory.get(k)
            if isinstance(condition, dict):
                op, target = next(iter(condition.items()))
                test = _OPS.get(op)
                if test is None or not test(v, target):
                    return False
            else:
                if v != condition:
                    return False
    return True


# ─── HMAC verification ────────────────────────────────────────────────
def _verify_provenance(db: Database, memory: dict) -> bool:
    prov = db[BELIEF_PROVENANCE].find_one(
        {"memory_id": memory["memory_id"]}, {"_id": 0}
    )
    if not prov:
        return False
    fields = signing_fields(memory, prov["source_text_hash"],
                            prov.get("tool_output_hashes", []))
    return verify(fields, prov["attestation"])


# ─── Logging ──────────────────────────────────────────────────────────
def _log_retrieval(db: Database, memory: dict, contract_id: str,
                   query_embedding: list[float], rank: int, agent_id: str,
                   filtered: bool) -> None:
    db[RETRIEVAL_LOG].insert_one({
        "ts": datetime.now(timezone.utc),
        "memory_id": memory["memory_id"],
        "query_embedding": query_embedding,
        "contract_id": contract_id,
        "retrieved_rank": rank,
        "score": memory.get("rrf_score", 0.0),
        "agent_id": agent_id,
        "filtered": filtered,
    })


# ─── Public API ───────────────────────────────────────────────────────
def retrieve(query_text: str, tool_context: dict) -> list[dict]:
    """Adaptive retrieval gated by belief contract. Logs every result."""
    return retrieve_with_audit(query_text, tool_context)["memories"]


def retrieve_with_audit(query_text: str, tool_context: dict) -> dict:
    """Returns {memories, filtered, contract} — frontend renders the filter reasons."""
    db = _db()
    tool_name = tool_context.get("tool_name", "lookup_order")
    user_id = tool_context.get("user_id")
    agent_id = tool_context.get("agent_id", "librarian")

    contract = get_contract(db, tool_name)
    query_embedding = embed_query(query_text)

    prefilter: dict[str, Any] = {"quarantined": False}
    if user_id:
        prefilter["user_id"] = user_id

    candidates = hybrid_retrieve(
        db, query_embedding, query_text,
        prefilter=prefilter, weights=contract["rank_weights"], limit=20,
    )

    passed: list[dict] = []
    filtered_out: list[dict] = []
    for rank, mem in enumerate(candidates):
        ok_filter = _passes_filters(mem, contract["filters"])
        ok_hmac = (
            _verify_provenance(db, mem)
            if contract.get("requires_hmac") else True
        )
        reasons: list[str] = []
        if not ok_filter:
            reasons.append("filter")
        if not ok_hmac:
            reasons.append("hmac")
        is_passed = not reasons

        _log_retrieval(db, mem, contract["contract_id"], query_embedding,
                       rank, agent_id, filtered=not is_passed)

        if is_passed:
            passed.append({**mem, "contract_id": contract["contract_id"]})
        else:
            filtered_out.append({
                "memory_id": mem["memory_id"],
                "drift_score": mem.get("drift_score"),
                "source_type": mem.get("source_type"),
                "reason": "+".join(reasons),
            })

    return {
        "memories": passed[:10],
        "filtered": filtered_out,
        "contract": {
            "contract_id": contract["contract_id"],
            "tier": contract["tier"],
            "rank_weights": contract["rank_weights"],
        },
    }


def retrieve_unprotected(query_text: str, tool_context: dict) -> list[dict]:
    """Control arm: same hybrid retrieval, NO contract filter, NO HMAC check.

    Logs to retrieval_log with agent_id='unprotected' and contract_id='none'
    so cohort variance is computed across both arms (this is the demo signal).
    """
    db = _db()
    user_id = tool_context.get("user_id")
    agent_id = tool_context.get("agent_id", "unprotected")

    query_embedding = embed_query(query_text)
    prefilter: dict[str, Any] = {"quarantined": False}
    if user_id:
        prefilter["user_id"] = user_id

    candidates = hybrid_retrieve(
        db, query_embedding, query_text,
        prefilter=prefilter, weights=None, limit=10,
    )
    for rank, mem in enumerate(candidates):
        _log_retrieval(db, mem, "none", query_embedding, rank, agent_id, filtered=False)
    return candidates
