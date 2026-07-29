"""Belief-provenance HMAC-SHA256 signing.

Every memory gets an attestation HMAC over its source_text_hash, tool_output_hashes,
parent_memory_id, user_id, thread_id, turn_number. An attacker can plant a memory but
cannot make it look like it came from a high-trust, tool-grounded source — the secret
lives server-side.

Production: secret in MongoDB Queryable Encryption.
Demo: HMAC_SECRET env var. PRD §4.1.
"""
from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import os
from typing import Any

_SECRET_ENV = "HMAC_SECRET"


def _secret() -> bytes:
    s = os.environ.get(_SECRET_ENV)
    if not s:
        raise RuntimeError(
            f"{_SECRET_ENV} not set — cannot sign or verify provenance. "
            "Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
        )
    return s.encode("utf-8")


def _canonical(fields: dict[str, Any]) -> bytes:
    """Canonical JSON: sorted keys, no whitespace, datetimes via str()."""
    return json.dumps(
        fields, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False
    ).encode("utf-8")


def sha256_hex(text: str) -> str:
    """SHA-256 of a UTF-8 string, hex-encoded. Used for source_text_hash."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sign(fields: dict[str, Any]) -> str:
    """Hex-encoded HMAC-SHA256 over canonical-JSON-serialised `fields`.

    Convention: caller passes only the immutable provenance-bearing fields, never
    drift_score / retrieval_count / etc. (those are mutated by Sentinel).
    """
    return _hmac.new(_secret(), _canonical(fields), hashlib.sha256).hexdigest()


def verify(fields: dict[str, Any], attestation: str) -> bool:
    """Constant-time comparison of computed vs claimed attestation."""
    try:
        expected = sign(fields)
        if len(attestation) != len(expected):
            return False
        return _hmac.compare_digest(expected, attestation)
    except Exception:
        return False


# Field set used for signing — keep this stable. Adding a field is a forking change.
PROVENANCE_FIELDS = (
    "memory_id",
    "source_text_hash",
    "tool_output_hashes",
    "parent_memory_id",
    "user_id",
    "thread_id",
    "turn_number",
)


def signing_fields(memory: dict[str, Any], source_text_hash: str,
                   tool_output_hashes: list[str] | None = None) -> dict[str, Any]:
    """Extract the canonical fields to feed into sign() from a Memory document."""
    return {
        "memory_id": memory["memory_id"],
        "source_text_hash": source_text_hash,
        "tool_output_hashes": tool_output_hashes or [],
        "parent_memory_id": memory.get("parent_memory_id"),
        "user_id": memory.get("user_id"),
        "thread_id": memory.get("thread_id"),
        "turn_number": memory.get("turn_number"),
    }


def verify_against_live_memory(memory: dict[str, Any],
                               provenance: dict[str, Any]) -> bool:
    """Fail closed unless live ``source_text`` still matches the signed hash.

    Verifying only the attestation over the *stored* ``source_text_hash`` is
    insufficient: an in-place edit to ``memories.source_text`` would keep a
    valid HMAC while the compliance bundle (and any retrieval gate that trusted
    the stored hash alone) reported integrity success for forged content.
    """
    if not memory or not provenance:
        return False
    live_hash = sha256_hex(memory.get("source_text") or "")
    if live_hash != provenance.get("source_text_hash"):
        return False
    fields = signing_fields(
        memory,
        provenance["source_text_hash"],
        provenance.get("tool_output_hashes", []),
    )
    return verify(fields, provenance.get("attestation") or "")
