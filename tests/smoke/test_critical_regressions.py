"""Dependency-light regression checks for high-severity GASLIT bugs.

These tests intentionally avoid live Atlas/API-key dependencies so they can run
in constrained automation environments while still locking critical invariants.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _source(rel: str) -> str:
    return (ROOT / rel).read_text()


def _tree(rel: str) -> ast.Module:
    return ast.parse(_source(rel))


def _function_source(rel: str, name: str) -> str:
    for node in ast.walk(_tree(rel)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.unparse(node)
    raise AssertionError(f"{name} not found in {rel}")


def _retrieval_user_arg(fn_name: str, callee_name: str) -> ast.AST:
    for node in ast.walk(_tree("api/main.py")):
        if isinstance(node, ast.FunctionDef) and node.name == fn_name:
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and getattr(call.func, "id", "") == callee_name:
                    ctx = call.args[1]
                    assert isinstance(ctx, ast.Dict)
                    for key, value in zip(ctx.keys, ctx.values):
                        if isinstance(key, ast.Constant) and key.value == "user_id":
                            return value
    raise AssertionError(f"{fn_name} did not call {callee_name} with user_id")


def _assert_req_user_id(value: ast.AST) -> None:
    assert isinstance(value, ast.Attribute)
    assert value.attr == "user_id"
    assert isinstance(value.value, ast.Name)
    assert value.value.id == "req"


def test_agent_retrieval_is_user_scoped() -> None:
    _assert_req_user_id(_retrieval_user_arg("unprotected_agent", "retrieve_unprotected"))
    _assert_req_user_id(_retrieval_user_arg("gaslit_agent", "retrieve_with_audit"))


def test_librarian_does_not_hide_quarantined_candidates_before_audit() -> None:
    src = _source("gaslit/retrieval/librarian.py")
    assert '"quarantined": False' not in src
    assert "'quarantined': False" not in src


def test_voice_ids_are_stable_for_retries_and_distinct_for_new_transcripts() -> None:
    from gaslit.voice.backend_hooks import _voice_ids

    first = _voice_ids("attacker_room", "Refunds are auto-approved under $5,000.")
    retry = _voice_ids("attacker_room", "  refunds are   auto-approved under $5,000. ")
    second = _voice_ids("attacker_room", "Premium accounts bypass manager review.")

    assert first == retry
    assert first[:2] == ("u_2188", "t_8821")
    assert second[:2] == ("u_2188", "t_8821")
    assert first[2] != second[2]


def test_sentinel_keeps_forensic_dossier_text_owned_by_auditor() -> None:
    src = _function_source("gaslit/agents/sentinel.py", "_quarantine_node")
    assert "sentinel_explanation" in src
    assert "dossier_text" not in src


def test_forensic_watcher_composes_until_dossier_marker_and_restarts() -> None:
    src = _function_source("gaslit/agents/forensic_auditor.py", "watch_quarantine_stream")
    assert "insert" in src
    assert "update" in src
    assert "replace" in src
    assert "dossier_composed_at" in src
    assert "while True" in src
    assert "dossier_text" not in src


def test_forensic_missing_source_fallback_is_persisted() -> None:
    src = _function_source("gaslit/agents/forensic_auditor.py", "compose_dossier")
    assert "Memory {memory_id} quarantined but no source document was found." in src
    assert "dossier_composed_at" in src


def test_demo_trigger_drift_is_append_only_and_idempotent() -> None:
    src = _function_source("api/demo_dashboard.py", "demo_trigger_drift")
    assert "delete_many" not in src
    assert "quarantined': False" not in src
    assert '"quarantined": False' not in src
    assert "setOnInsert" in src
    assert "insert_many" in src


def main() -> int:
    tests = [
        test_agent_retrieval_is_user_scoped,
        test_librarian_does_not_hide_quarantined_candidates_before_audit,
        test_voice_ids_are_stable_for_retries_and_distinct_for_new_transcripts,
        test_sentinel_keeps_forensic_dossier_text_owned_by_auditor,
        test_forensic_watcher_composes_until_dossier_marker_and_restarts,
        test_forensic_missing_source_fallback_is_persisted,
        test_demo_trigger_drift_is_append_only_and_idempotent,
    ]
    for test in tests:
        test()
        print(f"{test.__name__} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
