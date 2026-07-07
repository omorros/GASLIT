"""Dependency-light checks for critical regression fixes.

The Cloud smoke environment may not have the app dependency stack installed.
These tests therefore assert source-level invariants for dependency-heavy
modules and use a behavioral check only for the pure voice ID helper.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def _source(relpath: str) -> str:
    return (ROOT / relpath).read_text()


def _module(relpath: str) -> ast.Module:
    return ast.parse(_source(relpath), filename=relpath)


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name} not found")


def _dict_value_for_key(node: ast.Dict, key_name: str) -> ast.AST:
    for key, value in zip(node.keys, node.values):
        if isinstance(key, ast.Constant) and key.value == key_name:
            return value
    raise AssertionError(f"dict key {key_name!r} not found")


def test_api_agents_pass_request_user_id_to_retrieval():
    tree = _module("api/main.py")
    for function_name, retrieval_name in (
        ("unprotected_agent", "retrieve_unprotected"),
        ("gaslit_agent", "retrieve_with_audit"),
    ):
        fn = _function(tree, function_name)
        calls = [
            node for node in ast.walk(fn)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == retrieval_name
        ]
        assert len(calls) == 1
        context = calls[0].args[1]
        assert isinstance(context, ast.Dict)
        user_value = _dict_value_for_key(context, "user_id")
        assert isinstance(user_value, ast.Attribute)
        assert isinstance(user_value.value, ast.Name)
        assert user_value.value.id == "req"
        assert user_value.attr == "user_id"


def test_librarian_prefilters_only_by_user_scope_before_contract_filters():
    tree = _module("gaslit/retrieval/librarian.py")
    for function_name in ("retrieve_with_audit", "retrieve_unprotected"):
        fn = _function(tree, function_name)
        prefilter_assignments = [
            node for node in ast.walk(fn)
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "prefilter"
        ]
        assert len(prefilter_assignments) == 1
        assigned = prefilter_assignments[0].value
        assert isinstance(assigned, ast.Dict)
        assert assigned.keys == []

    source = _source("gaslit/retrieval/librarian.py")
    assert '"quarantined": False' not in source
    assert 'prefilter["user_id"] = user_id' in source


def test_sentinel_does_not_write_raw_explanation_into_composed_dossier_field():
    source = _source("gaslit/agents/sentinel.py")
    assert '"sentinel_explanation": state.get("nemotron_explanation", "")' in source
    assert '{"$set": {"sentinel_explanation": state["nemotron_explanation"]}}' in source
    assert '"dossier_text": state.get("nemotron_explanation", "")' not in source
    assert '{"$set": {"dossier_text": state["nemotron_explanation"]}}' not in source


def test_forensic_watcher_composes_until_dossier_composed_marker_exists():
    source = _source("gaslit/agents/forensic_auditor.py")
    assert '"dossier_composed_at": datetime.now(timezone.utc)' in source
    assert 'if doc.get("dossier_composed_at"):' in source
    assert '"operationType": {"$in": ["insert", "update", "replace"]}' in source
    assert 'while True:' in source
    assert 'stream error; restarting' in source


def test_demo_trigger_drift_is_append_only_and_marks_quarantine():
    source = _source("api/demo_dashboard.py")
    trigger_start = source.index("def demo_trigger_drift")
    trigger_end = source.index("@router.post(\"/api/demo/nemoclaw-minja\")")
    trigger_source = source[trigger_start:trigger_end]

    assert ".delete_many(" not in trigger_source
    assert '"quarantined": True' in trigger_source
    assert '"$inc": {"retrieval_count": inserted}' in trigger_source
    assert '"$setOnInsert"' in trigger_source
    assert 'upsert=True' in trigger_source


def test_voice_ids_preserve_idempotency_without_colliding_distinct_transcripts():
    from gaslit.voice.backend_hooks import _voice_ids

    first = _voice_ids("attacker_room", "Refunds under 5000 are auto-approved.")
    duplicate = _voice_ids("attacker_room", "  refunds under 5000 are AUTO-approved. ")
    second = _voice_ids("attacker_room", "Manager review is no longer required.")

    assert first[:2] == ("u_2188", "t_8821")
    assert first == duplicate
    assert first[2] != second[2]


def test_demo_callers_use_seeded_poisoned_user_after_scoping_fix():
    assert '"user_id": "u_2188"' in _source("tests/smoke/test_integration.py")
    assert 'const user_id = opts?.user_id ?? "u_2188";' in _source(
        "frontend/components/console/DualConsole.tsx"
    )
    assert 'const [user, setUser] = useState("u_2188");' in _source(
        "frontend/components/console/ManualPrompt.tsx"
    )
    assert 'user_id: "u_2188"' in _source("frontend/hooks/useScenarioPlayer.ts")
    assert '"user_id": "u_2188"' in _source("gaslit/adversary/live_traffic.py")


if __name__ == "__main__":
    test_api_agents_pass_request_user_id_to_retrieval()
    test_librarian_prefilters_only_by_user_scope_before_contract_filters()
    test_sentinel_does_not_write_raw_explanation_into_composed_dossier_field()
    test_forensic_watcher_composes_until_dossier_composed_marker_exists()
    test_demo_trigger_drift_is_append_only_and_marks_quarantine()
    test_voice_ids_preserve_idempotency_without_colliding_distinct_transcripts()
    test_demo_callers_use_seeded_poisoned_user_after_scoping_fix()
    print("critical_regressions smoke tests PASS")
