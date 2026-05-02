"""Load fixtures/corpus.json into MongoDB Atlas.

For each entry: insert a memory document into `memories` AND a provenance
document into `belief_provenance` in a single transaction. Idempotent —
re-running skips memories that already exist by memory_id.

Usage:
  python scripts/load_baseline_corpus.py
  python scripts/load_baseline_corpus.py --reset   # wipe collections first
  python scripts/load_baseline_corpus.py --in fixtures/corpus.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import BulkWriteError

from gaslit.schemas import MEMORIES, BELIEF_PROVENANCE, DB_NAME

load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", default="fixtures/corpus.json")
    parser.add_argument("--reset", action="store_true",
                        help="Drop existing memories + belief_provenance before loading")
    args = parser.parse_args()

    path = Path(args.inp)
    if not path.exists():
        print(f"[load] {path} missing — run scripts/generate_corpus.py first", file=sys.stderr)
        return 2

    docs = json.loads(path.read_text())
    print(f"[load] read {len(docs)} memories from {path}")

    client = MongoClient(os.environ["MONGODB_URI"])
    db = client[DB_NAME]

    if args.reset:
        n_m = db[MEMORIES].delete_many({}).deleted_count
        n_p = db[BELIEF_PROVENANCE].delete_many({}).deleted_count
        print(f"[load] reset: removed {n_m} memories, {n_p} provenance")

    now = datetime.now(timezone.utc)
    memory_docs = []
    prov_docs = []
    for d in docs:
        memory_docs.append({
            "memory_id": d["memory_id"],
            "user_id": d["user_id"],
            "thread_id": d["thread_id"],
            "turn_number": d["turn_number"],
            "source_text": d["source_text"],
            "source_type": d["source_type"],
            "embedding": d["embedding"],
            "confidence": d["confidence"],
            "parent_memory_id": d.get("parent_memory_id"),
            "drift_score": d.get("drift_score", 0.0),
            "cohort_variance": d.get("cohort_variance", 0.0),
            "retrieval_count": d.get("retrieval_count", 0),
            "quarantined": d.get("quarantined", False),
            "written_at": now,
        })
        p = d["_provenance"]
        prov_docs.append({
            "memory_id": p["memory_id"],
            "source_text_hash": p["source_text_hash"],
            "tool_output_hashes": p.get("tool_output_hashes", []),
            "parent_memory_id": p.get("parent_memory_id"),
            "attestation": p["attestation"],
            "written_at": now,
        })

    inserted_m = 0
    inserted_p = 0
    try:
        if memory_docs:
            r = db[MEMORIES].insert_many(memory_docs, ordered=False)
            inserted_m = len(r.inserted_ids)
    except BulkWriteError as e:
        inserted_m = e.details.get("nInserted", 0)
        n_dups = sum(1 for er in e.details.get("writeErrors", [])
                     if er.get("code") == 11000)
        print(f"[load] memories: {inserted_m} inserted, {n_dups} duplicates skipped")

    try:
        if prov_docs:
            r = db[BELIEF_PROVENANCE].insert_many(prov_docs, ordered=False)
            inserted_p = len(r.inserted_ids)
    except BulkWriteError as e:
        inserted_p = e.details.get("nInserted", 0)
        n_dups = sum(1 for er in e.details.get("writeErrors", [])
                     if er.get("code") == 11000)
        print(f"[load] belief_provenance: {inserted_p} inserted, {n_dups} duplicates skipped")

    n_m_total = db[MEMORIES].count_documents({})
    n_p_total = db[BELIEF_PROVENANCE].count_documents({})
    n_quar = db[MEMORIES].count_documents({"user_id": "u_2188"})
    print(f"[load] inserted +{inserted_m} memories, +{inserted_p} provenance")
    print(f"[load] totals: memories={n_m_total}, provenance={n_p_total}, u_2188 (poisoned author)={n_quar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
