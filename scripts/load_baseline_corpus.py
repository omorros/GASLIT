"""Load fixtures/corpus.json into MongoDB Atlas.

For each entry: insert a memory document into `memories` AND a provenance
document into `belief_provenance`. Idempotent — re-running skips memories
that already exist by memory_id and never re-signs live (possibly tampered)
documents.

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

from gaslit.provenance.hmac import sha256_hex, sign, signing_fields
from gaslit.schemas import MEMORIES, BELIEF_PROVENANCE, DB_NAME

load_dotenv()

# Fields that must match the fixture when a memory already exists. Mutating
# any of these and re-running the loader must fail closed — never mint a
# fresh attestation over the live document.
_IMMUTABLE_FIELDS = (
    "source_text",
    "source_type",
    "user_id",
    "thread_id",
    "turn_number",
    "parent_memory_id",
)


def _immutable_mismatch(live: dict, fixture: dict) -> list[str]:
    bad: list[str] = []
    for key in _IMMUTABLE_FIELDS:
        if live.get(key) != fixture.get(key):
            bad.append(key)
    return bad


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

    inserted_m = 0
    inserted_p = 0
    for memory_doc, fixture_doc in zip(memory_docs, docs):
        memory_result = db[MEMORIES].update_one(
            {"memory_id": memory_doc["memory_id"]},
            {"$setOnInsert": memory_doc},
            upsert=True,
        )
        if memory_result.upserted_id is not None:
            inserted_m += 1
        else:
            live_memory = db[MEMORIES].find_one(
                {"memory_id": memory_doc["memory_id"]}, {"_id": 0}
            ) or {}
            mismatch = _immutable_mismatch(live_memory, memory_doc)
            if mismatch:
                print(
                    f"[load] REFUSING to continue: {memory_doc['memory_id']} "
                    f"diverged from fixture on {', '.join(mismatch)}. "
                    "Use --reset to reload from fixtures, or restore the "
                    "canonical document before signing provenance.",
                    file=sys.stderr,
                )
                return 3

        # Always attest the fixture/canonical fields — never the live row.
        tool_output_hashes = fixture_doc.get("_provenance", {}).get("tool_output_hashes", [])
        source_text_hash = sha256_hex(memory_doc["source_text"])
        fields = signing_fields(memory_doc, source_text_hash, tool_output_hashes)
        provenance = {
            "memory_id": memory_doc["memory_id"],
            "source_text_hash": source_text_hash,
            "tool_output_hashes": tool_output_hashes,
            "parent_memory_id": memory_doc.get("parent_memory_id"),
            "attestation": sign(fields),
            "written_at": now,
        }
        # $setOnInsert keeps idempotent reloads from overwriting a good
        # attestation (or, worse, minting one for tampered live content).
        prov_result = db[BELIEF_PROVENANCE].update_one(
            {"memory_id": memory_doc["memory_id"]},
            {"$setOnInsert": provenance},
            upsert=True,
        )
        if prov_result.upserted_id is not None:
            inserted_p += 1

    n_m_total = db[MEMORIES].count_documents({})
    n_p_total = db[BELIEF_PROVENANCE].count_documents({})
    n_quar = db[MEMORIES].count_documents({"user_id": "u_2188"})
    print(f"[load] inserted +{inserted_m} memories, +{inserted_p} provenance attestations")
    print(f"[load] totals: memories={n_m_total}, provenance={n_p_total}, u_2188 (poisoned author)={n_quar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
