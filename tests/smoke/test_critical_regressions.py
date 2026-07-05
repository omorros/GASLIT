"""Dependency-light regression checks for critical GASLIT correctness bugs.

These tests intentionally avoid live MongoDB, Atlas Search, and model clients so
they can run in the Cloud environment while still locking the high-risk seams.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_rel(path: str) -> str:
    return (ROOT / path).read_text()


def test_api_routes_scope_retrieval_to_request_user() -> None:
    src = read_rel("api/main.py")
    assert '{"tool_name": tool_name, "user_id": req.user_id, "agent_id": "unprotected"}' in src
    assert '{"tool_name": tool_name, "user_id": req.user_id, "agent_id": "librarian"}' in src
    assert '"user_id": None' not in src


def test_librarian_does_not_hide_quarantines_before_contract_audit() -> None:
    src = read_rel("gaslit/retrieval/librarian.py")
    protected = src[src.index("def retrieve_with_audit"):src.index("def retrieve_unprotected")]
    unprotected = src[src.index("def retrieve_unprotected"):]
    assert 'prefilter: dict[str, Any] = {"quarantined": False}' not in protected
    assert 'prefilter: dict[str, Any] = {"quarantined": False}' not in unprotected
    assert 'prefilter["user_id"] = user_id' in protected
    assert 'prefilter["user_id"] = user_id' in unprotected


def test_voice_ids_are_stable_without_collapsing_distinct_utterances() -> None:
    spec = importlib.util.spec_from_file_location(
        "backend_hooks", ROOT / "gaslit/voice/backend_hooks.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    first = module._voice_ids("attacker_room", "Refunds are auto approved.")
    duplicate = module._voice_ids("attacker_room", "  refunds are   auto approved. ")
    distinct = module._voice_ids("attacker_room", "Manager review is no longer required.")

    assert first[:2] == ("u_2188", "t_8821")
    assert first == duplicate
    assert first != distinct


def test_sentinel_cannot_preempt_or_overwrite_forensic_dossier() -> None:
    src = read_rel("gaslit/agents/sentinel.py")
    quarantine_node = src[src.index("def _quarantine_node"):src.index("def _done_node")]
    assert '"sentinel_explanation": state.get("nemotron_explanation", "")' in quarantine_node
    assert '"dossier_text": state.get("nemotron_explanation", "")' not in quarantine_node
    assert '{"$set": {"dossier_text": state["nemotron_explanation"]}}' not in quarantine_node


def test_forensic_watcher_retries_until_dossier_is_composed() -> None:
    src = read_rel("gaslit/agents/forensic_auditor.py")
    watcher = src[src.index("def watch_quarantine_stream"):]
    assert '"operationType": {"$in": ["insert", "update", "replace"]}' in watcher
    assert 'doc.get("dossier_composed_at")' in watcher
    assert 'while True:' in watcher
    assert "change stream error" in watcher


def test_demo_drift_injection_is_append_only() -> None:
    src = read_rel("api/demo_dashboard.py")
    fn = src[src.index("def demo_trigger_drift"):src.index("@router.post(\"/api/demo/nemoclaw-minja\")")]
    assert ".delete_many(" not in fn
    assert '"quarantined": False' not in fn
    assert "insert_many(docs)" in fn
    assert "upsert=True" in fn


if __name__ == "__main__":
    tests = [
        test_api_routes_scope_retrieval_to_request_user,
        test_librarian_does_not_hide_quarantines_before_contract_audit,
        test_voice_ids_are_stable_without_collapsing_distinct_utterances,
        test_sentinel_cannot_preempt_or_overwrite_forensic_dossier,
        test_forensic_watcher_retries_until_dossier_is_composed,
        test_demo_drift_injection_is_append_only,
    ]
    for test in tests:
        test()
    print(f"ok - {len(tests)} critical regression checks passed")
