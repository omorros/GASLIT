"""Smoke test — HMAC sign / verify round-trip.

Asserts:
  1. sign() is deterministic (same input -> same output)
  2. verify() accepts a valid attestation
  3. verify() rejects when any signing field is mutated
  4. verify() rejects a forged attestation
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from gaslit.provenance.hmac import sign, verify, signing_fields, sha256_hex


def _make():
    memory = {
        "memory_id": "m_test_001",
        "user_id": "u_alice",
        "thread_id": "t_001",
        "turn_number": 1,
    }
    src = "Refunds for premium accounts are auto-approved under $5,000."
    fields = signing_fields(memory, sha256_hex(src), [])
    return memory, fields


def test_deterministic():
    _, fields = _make()
    assert sign(fields) == sign(fields)


def test_round_trip():
    _, fields = _make()
    assert verify(fields, sign(fields))


def test_rejects_tampered_text():
    memory, fields = _make()
    sig = sign(fields)
    fields["source_text_hash"] = sha256_hex("DIFFERENT TEXT")
    assert not verify(fields, sig)


def test_rejects_forged_attestation():
    _, fields = _make()
    assert not verify(fields, "deadbeef" * 8)


def test_rejects_user_swap():
    memory, fields = _make()
    sig = sign(fields)
    fields["user_id"] = "u_attacker"
    assert not verify(fields, sig)


if __name__ == "__main__":
    test_deterministic()
    test_round_trip()
    test_rejects_tampered_text()
    test_rejects_forged_attestation()
    test_rejects_user_swap()
    print("hmac_provenance smoke tests PASS")
