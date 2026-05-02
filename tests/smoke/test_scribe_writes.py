"""Smoke test — Scribe writes a memory + provenance atomically.

Requires Atlas reachable + ANTHROPIC_API_KEY + VOYAGE_API_KEY live.

Usage:
  python tests/smoke/test_scribe_writes.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
from pymongo import MongoClient

from gaslit.agents.scribe import scribe_turn, write_memory, deterministic_memory_id
from gaslit.provenance.hmac import verify, signing_fields
from gaslit.schemas import MEMORIES, BELIEF_PROVENANCE, DB_NAME

load_dotenv()


TEST_USER = "u_smoketest"
TEST_THREAD = "t_smoketest"


def main() -> int:
    db = MongoClient(os.environ["MONGODB_URI"])[DB_NAME]
    expected_mid = deterministic_memory_id(TEST_USER, TEST_THREAD, 1)

    # Cleanup any prior smoke artefacts
    db[MEMORIES].delete_many({"user_id": TEST_USER})
    db[BELIEF_PROVENANCE].delete_many({"memory_id": expected_mid})

    # 1. Skip distil — write_memory directly so we don't burn an Anthropic call
    mem = write_memory(
        user_id=TEST_USER,
        thread_id=TEST_THREAD,
        turn_number=1,
        source_text="The user prefers email notifications over SMS for security alerts.",
        source_type="user_distillation",
        confidence=0.7,
    )
    mid = mem["memory_id"]
    assert mid == expected_mid, f"memory_id mismatch: {mid} vs {expected_mid}"

    # 2. Verify both collections wrote atomically
    m = db[MEMORIES].find_one({"memory_id": mid})
    p = db[BELIEF_PROVENANCE].find_one({"memory_id": mid})
    assert m is not None, "memory not in memories"
    assert p is not None, "memory not in belief_provenance"
    assert len(m["embedding"]) == 1024, f"wrong embedding dim {len(m['embedding'])}"
    assert m["confidence"] == 0.7
    assert m["quarantined"] is False
    assert m["drift_score"] == 0.0

    # 3. Verify HMAC round-trip
    fields = signing_fields(m, p["source_text_hash"], p.get("tool_output_hashes", []))
    assert verify(fields, p["attestation"]), "HMAC verify failed on freshly-written memory"

    # 4. Idempotency — second call with same (user, thread, turn) is a no-op
    mem2 = write_memory(
        user_id=TEST_USER,
        thread_id=TEST_THREAD,
        turn_number=1,
        source_text="DIFFERENT TEXT — should not overwrite",
        source_type="user_distillation",
        confidence=0.7,
    )
    n_m = db[MEMORIES].count_documents({"user_id": TEST_USER, "thread_id": TEST_THREAD,
                                        "turn_number": 1})
    assert n_m == 1, f"expected 1 memory after duplicate write, got {n_m}"

    # Cleanup
    db[MEMORIES].delete_many({"user_id": TEST_USER})
    db[BELIEF_PROVENANCE].delete_many({"memory_id": mid})

    print("scribe_writes smoke test PASS — atomic + HMAC verified + idempotent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
