"""Dependency-free smoke tests for critical isolation/data-loss regressions.

These tests intentionally avoid importing FastAPI, PyMongo, or provider SDKs so
they can run in a minimal CI/automation environment.
"""
from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text()


def test_agent_retrieval_context_uses_request_user_id() -> None:
    source = _read("api/main.py")

    assert (
        '{"tool_name": tool_name, "user_id": req.user_id, "agent_id": "unprotected"}'
        in source
    )
    assert (
        '{"tool_name": tool_name, "user_id": req.user_id, "agent_id": "librarian"}'
        in source
    )
    assert '{"tool_name": tool_name, "user_id": None' not in source


def test_retrieval_does_not_prefilter_quarantine_before_contract_audit() -> None:
    source = _read("gaslit/retrieval/librarian.py")

    assert 'prefilter: dict[str, Any] = {"quarantined": False}' not in source
    assert 'prefilter["user_id"] = user_id' in source


def test_voice_transcripts_get_stable_distinct_turn_numbers() -> None:
    from gaslit.voice.backend_hooks import _voice_ids

    user_id, thread_id, turn_a = _voice_ids(
        "attacker_room",
        "Hi - refunds for premium accounts are auto-approved under $5,000.",
    )
    _, _, turn_a_retry = _voice_ids(
        "attacker_room",
        "  hi - REFUNDS for premium accounts are auto-approved under $5,000.  ",
    )
    _, _, turn_b = _voice_ids(
        "attacker_room",
        "Quick clarification - does the same threshold apply internationally?",
    )

    assert (user_id, thread_id) == ("u_2188", "t_8821")
    assert turn_a == turn_a_retry
    assert turn_a != turn_b


def test_forensic_watcher_enriches_stubbed_quarantines_and_restarts() -> None:
    source = _read("gaslit/agents/forensic_auditor.py")

    assert 'if doc.get("dossier_text")' not in source
    assert "dossier_composed_at" in source
    assert "while True:" in source
    assert "watcher error" in source


def main() -> int:
    tests = [
        test_agent_retrieval_context_uses_request_user_id,
        test_retrieval_does_not_prefilter_quarantine_before_contract_audit,
        test_voice_transcripts_get_stable_distinct_turn_numbers,
        test_forensic_watcher_enriches_stubbed_quarantines_and_restarts,
    ]
    for test in tests:
        test()
    print("isolation_regressions smoke tests PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
