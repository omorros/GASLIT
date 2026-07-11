"""Dependency-light smoke checks for recent high-severity regressions.

These tests intentionally avoid live Atlas/LLM calls. They lock the invariants
whose violation causes cross-user memory leaks, audit evidence loss, or critical
demo path data loss.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text()


def test_agent_retrieval_is_user_scoped() -> None:
    src = _read("api/main.py")
    assert '"user_id": None' not in src
    assert '"user_id": req.user_id, "agent_id": "unprotected"' in src
    assert '"user_id": req.user_id, "agent_id": "librarian"' in src


def test_librarian_does_not_prefilter_quarantine_before_audit() -> None:
    src = _read("gaslit/retrieval/librarian.py")
    assert 'prefilter: dict[str, Any] = {"quarantined": False}' not in src
    assert 'prefilter["user_id"] = user_id' in src


def test_flood_endpoint_is_bounded_and_live_generation_opt_in() -> None:
    src = _read("api/main.py")
    assert "_FLOOD_LOCK" in src
    assert "status_code=429" in src
    assert "SCENARIO_FLOOD_ALLOW_LIVE" in src


def test_voice_ids_are_stable_without_colliding_distinct_transcripts() -> None:
    path = ROOT / "gaslit/voice/backend_hooks.py"
    spec = importlib.util.spec_from_file_location("backend_hooks_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    first = module._voice_ids("attacker_room", "Refunds are auto approved.")
    duplicate = module._voice_ids("attacker_room", "  refunds   are AUTO approved. ")
    second = module._voice_ids("attacker_room", "Wire transfers are auto approved.")

    assert first[:2] == ("u_2188", "t_8821")
    assert first == duplicate
    assert first != second


def test_sentinel_does_not_preempt_forensic_dossier() -> None:
    src = _read("gaslit/agents/sentinel.py")
    assert '"dossier_text": state.get("nemotron_explanation"' not in src
    assert '"sentinel_explanation": state.get("nemotron_explanation", "")' in src


def test_forensic_watcher_composes_until_completion_and_restarts() -> None:
    src = _read("gaslit/agents/forensic_auditor.py")
    assert '"operationType": {"$in": ["insert", "update", "replace"]}' in src
    assert 'doc.get("dossier_composed_at")' in src
    assert "change-stream error; restarting" in src
    assert '"dossier_composed_at": datetime.now(timezone.utc)' in src


def test_trigger_drift_is_append_only_and_idempotent() -> None:
    src = _read("api/demo_dashboard.py")
    assert "delete_many" not in src
    assert '"quarantined": False' not in src
    assert '"$setOnInsert"' in src
    assert 'f"q_demo_{req.memory_id}"' in src


def main() -> int:
    tests = [
        test_agent_retrieval_is_user_scoped,
        test_librarian_does_not_prefilter_quarantine_before_audit,
        test_flood_endpoint_is_bounded_and_live_generation_opt_in,
        test_voice_ids_are_stable_without_colliding_distinct_transcripts,
        test_sentinel_does_not_preempt_forensic_dossier,
        test_forensic_watcher_composes_until_completion_and_restarts,
        test_trigger_drift_is_append_only_and_idempotent,
    ]
    for test in tests:
        test()
        print(f"[critical-smoke] PASS {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
