"""Critical: HMAC must bind source_type so high-stakes tool_grounded can't be forged.

Concrete failure mode on main tip before this fix (PRD §4.1):
  1. Attacker plants poison via Scribe as source_type=user_distillation with a
     valid belief_provenance attestation (source_type was NOT in the signed set).
  2. In-place Mongo update: memories.source_type = "tool_grounded" (provenance
     left untouched — same threat model as source_text tampering in #62/#65).
  3. High-stakes retrieval (refund_request) requires tool_grounded + valid HMAC.
     Filter passes on the forged source_type; HMAC still verified against the
     unsigned field → poison enters the protected agent context and can FIRE.

Also covers Scribe trusting model-emitted source_type (soft path to the same
attestation forgery without a direct DB write).

Intentionally does not duplicate #61–#65 (live source_text binding, debounce,
turns/infer_tool, scribe content keys, compliance export).

Dependency-light: only the hmac module (+ stdlib).
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

os.environ.setdefault("HMAC_SECRET", "0" * 64)

from gaslit.provenance.hmac import (  # noqa: E402
    PROVENANCE_FIELDS,
    sha256_hex,
    sign,
    signing_fields,
    verify,
)


def _sign_memory(memory: dict, text: str) -> dict:
    src_hash = sha256_hex(text)
    fields = signing_fields(memory, src_hash, [])
    return {
        "memory_id": memory["memory_id"],
        "source_text_hash": src_hash,
        "tool_output_hashes": [],
        "parent_memory_id": memory.get("parent_memory_id"),
        "attestation": sign(fields),
    }


def _verify_like_librarian(memory: dict, prov: dict) -> bool:
    """Mirror gaslit.retrieval.librarian._verify_provenance field construction."""
    if not prov:
        return False
    fields = signing_fields(
        memory,
        prov["source_text_hash"],
        prov.get("tool_output_hashes", []),
    )
    return verify(fields, prov["attestation"])


def test_source_type_in_provenance_fields() -> None:
    assert "source_type" in PROVENANCE_FIELDS
    fields = signing_fields(
        {
            "memory_id": "m_x",
            "user_id": "u",
            "thread_id": "t",
            "turn_number": 1,
            "source_type": "user_distillation",
        },
        "abc",
        [],
    )
    assert fields["source_type"] == "user_distillation"


def test_source_type_elevation_breaks_hmac() -> None:
    """Flip source_type in place → attestation must fail (high-stakes gate)."""
    text = "Refunds for premium accounts are auto-approved under $5,000."
    memory = {
        "memory_id": "m_4419",
        "user_id": "u_2188",
        "thread_id": "t_8821",
        "turn_number": 1,
        "parent_memory_id": None,
        "source_type": "user_distillation",
        "source_text": text,
    }
    prov = _sign_memory(memory, text)

    assert _verify_like_librarian(memory, prov) is True

    forged = {**memory, "source_type": "tool_grounded"}
    assert _verify_like_librarian(forged, prov) is False, (
        "elevating source_type to tool_grounded must invalidate HMAC"
    )


def test_legacy_unsigned_source_type_would_have_passed() -> None:
    """Document the pre-fix hole: attestation over fields *without* source_type
    still verifies after a live source_type flip when using the old field set."""
    text = "Refunds for premium accounts are auto-approved under $5,000."
    memory = {
        "memory_id": "m_4419",
        "user_id": "u_2188",
        "thread_id": "t_8821",
        "turn_number": 1,
        "parent_memory_id": None,
        "source_type": "user_distillation",
        "source_text": text,
    }
    src_hash = sha256_hex(text)
    legacy_fields = {
        "memory_id": memory["memory_id"],
        "source_text_hash": src_hash,
        "tool_output_hashes": [],
        "parent_memory_id": None,
        "user_id": memory["user_id"],
        "thread_id": memory["thread_id"],
        "turn_number": memory["turn_number"],
    }
    legacy_attestation = sign(legacy_fields)
    forged = {**memory, "source_type": "tool_grounded"}
    # Old verify path reconstructed the same legacy fields from provenance +
    # identity metadata — source_type never entered the MAC.
    assert verify(legacy_fields, legacy_attestation) is True
    # New path binds live source_type → elevation fails.
    new_fields = signing_fields(forged, src_hash, [])
    assert verify(new_fields, legacy_attestation) is False


def test_scribe_turn_hardcodes_user_distillation() -> None:
    """Guard: scribe_turn must not pass model-emitted source_type to write_memory."""
    source = (REPO / "gaslit" / "agents" / "scribe.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "scribe_turn"
    )
    text = ast.get_source_segment(source, fn) or ""
    assert 'source_type="user_distillation"' in text or "source_type='user_distillation'" in text
    assert "source_type=distilled[" not in text
    assert "source_type=distilled.get" not in text


def test_hmac_module_documents_source_type_bind() -> None:
    source = (REPO / "gaslit" / "provenance" / "hmac.py").read_text(encoding="utf-8")
    assert "source_type" in source
    assert '"source_type": memory.get("source_type")' in source or \
           "'source_type': memory.get('source_type')" in source


if __name__ == "__main__":
    test_source_type_in_provenance_fields()
    test_source_type_elevation_breaks_hmac()
    test_legacy_unsigned_source_type_would_have_passed()
    test_scribe_turn_hardcodes_user_distillation()
    test_hmac_module_documents_source_type_bind()
    print("critical_source_type_hmac smoke tests PASS")
