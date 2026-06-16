"""Dependency-light regression tests for critical demo correctness paths.

These tests intentionally avoid live MongoDB/provider calls. They lock the
source-level invariants that previously caused data loss or demo breakage.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def _read(rel: str) -> str:
    return (ROOT / rel).read_text()


def test_voice_ids_are_stable_without_colliding_distinct_transcripts():
    from gaslit.voice.backend_hooks import _voice_ids

    first = _voice_ids("attacker_room", "Premium refunds are auto-approved.")
    duplicate = _voice_ids("attacker_room", "  Premium refunds   are auto-approved. ")
    second = _voice_ids("attacker_room", "Manager review is no longer required.")

    assert first == duplicate
    assert first[:2] == ("u_2188", "t_8821")
    assert second[:2] == ("u_2188", "t_8821")
    assert first[2] != second[2]


def test_sentinel_explanation_does_not_preempt_forensic_dossier():
    src = _read("gaslit/agents/sentinel.py")

    assert '"sentinel_explanation": state.get("nemotron_explanation", "")' in src
    assert '"dossier_text": state.get("nemotron_explanation", "")' not in src
    assert '"$set": {"sentinel_explanation": state["nemotron_explanation"]}' in src
    assert '"$set": {"dossier_text": state["nemotron_explanation"]}' not in src


def test_forensic_watcher_composes_until_dossier_composed():
    src = _read("gaslit/agents/forensic_auditor.py")

    assert '"operationType": {"$in": ["insert", "update", "replace"]}' in src
    assert 'doc.get("dossier_composed_at")' in src
    assert "while True:" in src
    assert '"dossier_composed_at": datetime.now(timezone.utc)' in src


def test_retrieval_keeps_quarantine_as_contract_filter_not_prefilter():
    src = _read("gaslit/retrieval/librarian.py")

    assert 'prefilter: dict[str, Any] = {"quarantined": False}' not in src
    assert src.count("prefilter: dict[str, Any] = {}") == 2


def test_trigger_drift_is_append_only_and_creates_demo_quarantine():
    src = _read("api/demo_dashboard.py")

    body = src.split('def demo_trigger_drift(req: TriggerDriftReq) -> TriggerDriftResp:', 1)[1]
    body = body.split('@router.post("/api/demo/nemoclaw-minja")', 1)[0]

    assert ".delete_many(" not in body
    assert '"quarantined": True' in body
    assert '"$setOnInsert"' in body
    assert '"sentinel_explanation": (' in body


def test_internal_demo_clients_default_to_documented_api_port():
    for rel in (
        "gaslit/adversary/live_traffic.py",
        "gaslit/adversary/minja_simulator.py",
        "tests/smoke/test_integration.py",
    ):
        src = _read(rel)
        assert "os.environ.get('API_PORT', '8002')" in src
        assert "os.environ.get('API_PORT', '8000')" not in src


if __name__ == "__main__":
    test_voice_ids_are_stable_without_colliding_distinct_transcripts()
    test_sentinel_explanation_does_not_preempt_forensic_dossier()
    test_forensic_watcher_composes_until_dossier_composed()
    test_retrieval_keeps_quarantine_as_contract_filter_not_prefilter()
    test_trigger_drift_is_append_only_and_creates_demo_quarantine()
    test_internal_demo_clients_default_to_documented_api_port()
    print("critical_regressions smoke tests PASS")
