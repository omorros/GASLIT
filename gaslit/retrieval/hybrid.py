"""Hybrid retrieval — three parallel arms + Reciprocal Rank Fusion in Python.

Why not $rankFusion-with-$vectorSearch as a single stage? Because that requires
MongoDB 8.1+, and our Atlas cluster is pinned to 8.0.22 by the org's resource
policy (PRD §7). So we run three parallel aggregations in threads and merge
with weighted RRF in Python. Mathematically equivalent to the 8.1+ form.

Three arms:
1. $vectorSearch on memories.embedding (Voyage 3 large, 1024-dim cosine)
2. $search BM25 on memories.source_text
3. $search BM25 on belief_provenance.source_text_hash (provenance arm)

Per-contract weights apply at merge.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from pymongo.database import Database

from gaslit.schemas import (
    MEMORIES, BELIEF_PROVENANCE, VECTOR_INDEX, TEXT_INDEX, PROVENANCE_TEXT_INDEX,
    RRF_K, DEFAULT_RANK_WEIGHTS,
)


# ─── Three arms ───────────────────────────────────────────────────────
def _vector_search(db: Database, query_embedding: list[float],
                   prefilter: dict, num_candidates: int, limit: int) -> list[dict]:
    stage: dict[str, Any] = {
        "index": VECTOR_INDEX,
        "path": "embedding",
        "queryVector": query_embedding,
        "numCandidates": num_candidates,
        "limit": limit,
    }
    if prefilter:
        stage["filter"] = prefilter
    pipeline = [
        {"$vectorSearch": stage},
        {"$set": {"_arm_score": {"$meta": "vectorSearchScore"}}},
        {"$project": {"embedding": 0}},
    ]
    return list(db[MEMORIES].aggregate(pipeline))


def _text_search(db: Database, query_text: str,
                 prefilter: dict, limit: int) -> list[dict]:
    must = [{"text": {"query": query_text, "path": "source_text"}}]
    filter_clauses = _prefilter_to_search_filter(prefilter) if prefilter else []
    search_stage: dict[str, Any] = {
        "index": TEXT_INDEX,
        "compound": {"must": must},
    }
    if filter_clauses:
        search_stage["compound"]["filter"] = filter_clauses
    pipeline = [
        {"$search": search_stage},
        {"$limit": limit},
        {"$set": {"_arm_score": {"$meta": "searchScore"}}},
        {"$project": {"embedding": 0}},
    ]
    return list(db[MEMORIES].aggregate(pipeline))


def _provenance_search(db: Database, query_text: str, limit: int) -> list[dict]:
    """BM25 on belief_provenance.source_text_hash. Returns memory_id refs only.

    The hashes are short (SHA-256 hex). They're indexed because we want to
    detect when an attacker re-uses the same source_text_hash — useful in
    forensics, less useful in retrieval. Kept for completeness per PRD §7.
    """
    pipeline = [
        {"$search": {
            "index": PROVENANCE_TEXT_INDEX,
            "text": {"query": query_text, "path": "source_text_hash"},
        }},
        {"$limit": limit},
        {"$set": {"_arm_score": {"$meta": "searchScore"}}},
        {"$project": {"memory_id": 1, "_arm_score": 1}},
    ]
    return list(db[BELIEF_PROVENANCE].aggregate(pipeline))


def _prefilter_to_search_filter(prefilter: dict) -> list[dict]:
    """Translate a {field: value} prefilter into Atlas Search filter clauses."""
    out: list[dict] = []
    for k, v in prefilter.items():
        if isinstance(v, bool):
            out.append({"equals": {"path": k, "value": v}})
        elif isinstance(v, str):
            out.append({"equals": {"path": k, "value": v}})
        elif isinstance(v, list):
            out.append({"in": {"path": k, "value": v}})
    return out


# ─── RRF merge ────────────────────────────────────────────────────────
def rrf_merge(arms: dict[str, list[dict]], weights: dict[str, float],
              k: int = RRF_K, limit: int = 10) -> list[dict]:
    """Reciprocal Rank Fusion over named arms.

    Score(memory) = sum_{arm} weight[arm] * 1 / (k + rank_in_arm + 1)
    Bigger is better. Returns memories sorted by combined score.

    Documents from the provenance arm only carry memory_id; callers should
    hydrate from `memories` before calling rrf_merge if they want full docs.
    """
    scores: dict[str, float] = {}
    by_id: dict[str, dict] = {}

    for arm_name, docs in arms.items():
        weight = weights.get(arm_name, 0.0)
        if weight == 0.0 or not docs:
            continue
        for rank, doc in enumerate(docs):
            mid = doc.get("memory_id")
            if not mid:
                continue
            scores[mid] = scores.get(mid, 0.0) + weight * (1.0 / (k + rank + 1))
            existing = by_id.get(mid)
            if existing is None:
                by_id[mid] = doc
            elif not existing.get("source_text") and doc.get("source_text"):
                # Prefer hydrated docs over provenance-arm stubs.
                by_id[mid] = doc

    ordered = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]
    out: list[dict] = []
    for mid, s in ordered:
        merged = dict(by_id[mid])
        merged["rrf_score"] = s
        merged.pop("_arm_score", None)
        out.append(merged)
    return out


# ─── Entry point ──────────────────────────────────────────────────────
def hybrid_retrieve(db: Database, query_embedding: list[float], query_text: str,
                    *, prefilter: Optional[dict] = None,
                    weights: Optional[dict] = None,
                    limit: int = 10, num_candidates: int = 200) -> list[dict]:
    """Run all three arms in parallel, hydrate provenance, RRF-merge."""
    weights = weights or DEFAULT_RANK_WEIGHTS
    prefilter = prefilter or {}

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_vec = ex.submit(_vector_search, db, query_embedding, prefilter, num_candidates, 50)
        f_txt = ex.submit(_text_search, db, query_text, prefilter, 50)
        f_prv = ex.submit(_provenance_search, db, query_text, 50)
        vec, txt, prv = f_vec.result(), f_txt.result(), f_prv.result()

    if prv:
        ids = [d["memory_id"] for d in prv]
        memos = list(db[MEMORIES].find(
            {"memory_id": {"$in": ids}, **prefilter},
            {"embedding": 0},
        ))
        memo_by_id = {m["memory_id"]: m for m in memos}
        prv_hydrated: list[dict] = []
        for d in prv:
            base = memo_by_id.get(d["memory_id"])
            if base is None:
                continue
            prv_hydrated.append({**base, "_arm_score": d["_arm_score"]})
        prv = prv_hydrated

    return rrf_merge(
        {"vector": vec, "text": txt, "provenance": prv},
        weights, k=RRF_K, limit=limit,
    )
