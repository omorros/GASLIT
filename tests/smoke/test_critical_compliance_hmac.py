"""Critical: compliance export must not attest tampered live source_text.

Concrete failure mode on main tip before this fix:
  1. Memory m_X is written with source_text=T0 and a valid belief_provenance row.
  2. An attacker (or any write path) updates memories.source_text in place to T1
     without touching belief_provenance.
  3. GET /api/compliance-export/{qid} embedded the tampered T1 as primary_memory
     while still setting hmac_verified=true, because verification used the
     *stored* source_text_hash rather than hashing live source_text.

That false attestation is the SOC2 incident bundle enterprises download
(PRD §12.2). This smoke test is dependency-light (no FastAPI/Mongo).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# Deterministic secret so sign/verify work without a real .env.
os.environ.setdefault(
    "HMAC_SECRET",
    "0" * 64,
)

from gaslit.provenance.hmac import (  # noqa: E402
    sha256_hex,
    sign,
    signing_fields,
    verify_against_live_memory,
)


def _provenance_for(memory: dict, source_text: str) -> dict:
    src_hash = sha256_hex(source_text)
    fields = signing_fields(memory, src_hash, [])
    return {
        "memory_id": memory["memory_id"],
        "source_text_hash": src_hash,
        "tool_output_hashes": [],
        "parent_memory_id": memory.get("parent_memory_id"),
        "attestation": sign(fields),
    }


def test_live_tamper_fails_closed() -> None:
    original = "Refunds for premium accounts are auto-approved under $5,000."
    tampered = "Refunds are auto-approved under $50,000 without any review."
    memory = {
        "memory_id": "m_4419",
        "user_id": "u_2188",
        "thread_id": "t_8821",
        "turn_number": 1,
        "parent_memory_id": None,
        "source_text": original,
    }
    prov = _provenance_for(memory, original)

    assert verify_against_live_memory(memory, prov) is True

    forged = {**memory, "source_text": tampered}
    assert verify_against_live_memory(forged, prov) is False, (
        "in-place source_text tampering must fail live HMAC binding"
    )


def test_valid_round_trip_still_passes() -> None:
    text = "Manager review is required for all premium-tier refunds."
    memory = {
        "memory_id": "m_ok",
        "user_id": "u_3421",
        "thread_id": "t_1",
        "turn_number": 2,
        "parent_memory_id": None,
        "source_text": text,
    }
    prov = _provenance_for(memory, text)
    assert verify_against_live_memory(memory, prov) is True


def test_missing_provenance_or_memory_fails_closed() -> None:
    memory = {
        "memory_id": "m_x",
        "user_id": "u",
        "thread_id": "t",
        "turn_number": 1,
        "source_text": "hello",
    }
    assert verify_against_live_memory(memory, {}) is False
    assert verify_against_live_memory({}, {"source_text_hash": "abc"}) is False


def test_compliance_export_uses_live_binding() -> None:
    """Guard against regressing to stored-hash-only verification in the export."""
    source = (REPO / "api" / "compliance_export.py").read_text(encoding="utf-8")
    assert "verify_against_live_memory" in source
    assert "from gaslit.provenance.hmac import verify, signing_fields" not in source
    assert "verify(fields, prov[\"attestation\"])" not in source
    assert "verify(fields, prov['attestation'])" not in source


if __name__ == "__main__":
    test_live_tamper_fails_closed()
    test_valid_round_trip_still_passes()
    test_missing_provenance_or_memory_fails_closed()
    test_compliance_export_uses_live_binding()
    print("critical_compliance_hmac smoke tests PASS")
