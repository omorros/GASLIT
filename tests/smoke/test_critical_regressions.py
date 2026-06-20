"""Dependency-light regression checks for critical GASLIT correctness paths.

These tests avoid live Atlas/API/provider calls. They lock in the invariants
that protect tenant isolation, quarantine auditability, append-only evidence,
forensic dossier ownership, and idempotent voice transcript writes.
"""
from __future__ import annotations

import ast
import importlib
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _read_module_ast(path: str) -> ast.Module:
    return ast.parse((ROOT / path).read_text(), filename=path)


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def test_api_retrieval_uses_request_user_id() -> None:
    tree = _read_module_ast("api/main.py")
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _call_name(node) in {"retrieve_unprotected", "retrieve_with_audit"}
    ]
    assert len(calls) == 2, f"expected two retrieval calls, got {len(calls)}"

    for call in calls:
        assert len(call.args) >= 2 and isinstance(call.args[1], ast.Dict)
        context = call.args[1]
        user_values = [
            value for key, value in zip(context.keys, context.values)
            if isinstance(key, ast.Constant) and key.value == "user_id"
        ]
        assert len(user_values) == 1
        user_value = user_values[0]
        assert isinstance(user_value, ast.Attribute)
        assert isinstance(user_value.value, ast.Name)
        assert user_value.value.id == "req"
        assert user_value.attr == "user_id"


def _install_dependency_stubs() -> None:
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules.setdefault("dotenv", dotenv)

    pymongo = types.ModuleType("pymongo")
    pymongo.MongoClient = lambda *args, **kwargs: None
    pymongo_database = types.ModuleType("pymongo.database")
    pymongo_database.Database = object
    pymongo.database = pymongo_database
    sys.modules.setdefault("pymongo", pymongo)
    sys.modules.setdefault("pymongo.database", pymongo_database)

    embeddings = types.ModuleType("gaslit.embeddings")
    embeddings.embed_query = lambda text: [0.0]
    sys.modules.setdefault("gaslit.embeddings", embeddings)


class _FakeCollection:
    def __init__(self) -> None:
        self.inserted: list[dict] = []

    def insert_one(self, doc: dict) -> None:
        self.inserted.append(doc)


class _FakeDB:
    def __init__(self) -> None:
        self.collections: dict[str, _FakeCollection] = {}

    def __getitem__(self, name: str) -> _FakeCollection:
        self.collections.setdefault(name, _FakeCollection())
        return self.collections[name]


def test_retrieval_prefilter_only_scopes_user_and_audits_quarantine() -> None:
    _install_dependency_stubs()
    librarian = importlib.import_module("gaslit.retrieval.librarian")

    captured_prefilters: list[dict] = []
    fake_db = _FakeDB()
    candidates = [
        {
            "memory_id": "m_quarantined",
            "user_id": "u_1",
            "quarantined": True,
            "drift_score": 0.91,
            "source_type": "user_distillation",
        },
        {
            "memory_id": "m_clean",
            "user_id": "u_1",
            "quarantined": False,
            "drift_score": 0.0,
            "source_type": "tool_grounded",
        },
    ]
    contract = {
        "contract_id": "high_stakes_refund_request",
        "tier": "high_stakes",
        "filters": [{"quarantined": False}],
        "rank_weights": {"vector": 1.0, "text": 0.0, "provenance": 0.0},
        "requires_hmac": False,
    }

    originals = {
        "_db": librarian._db,
        "embed_query": librarian.embed_query,
        "hybrid_retrieve": librarian.hybrid_retrieve,
        "get_contract": librarian.get_contract,
    }

    def fake_hybrid(db, query_embedding, query_text, *, prefilter, weights, limit):
        captured_prefilters.append(dict(prefilter))
        return list(candidates)

    try:
        librarian._db = lambda: fake_db
        librarian.embed_query = lambda text: [0.1, 0.2]
        librarian.hybrid_retrieve = fake_hybrid
        librarian.get_contract = lambda db, tool_name: contract

        audit = librarian.retrieve_with_audit(
            "refund request",
            {"tool_name": "refund_request", "user_id": "u_1", "agent_id": "librarian"},
        )
        assert captured_prefilters[-1] == {"user_id": "u_1"}
        assert [m["memory_id"] for m in audit["memories"]] == ["m_clean"]
        assert [m["memory_id"] for m in audit["filtered"]] == ["m_quarantined"]

        unprotected = librarian.retrieve_unprotected(
            "refund request",
            {"tool_name": "refund_request", "user_id": "u_1", "agent_id": "unprotected"},
        )
        assert captured_prefilters[-1] == {"user_id": "u_1"}
        assert [m["memory_id"] for m in unprotected] == ["m_quarantined", "m_clean"]
    finally:
        for name, value in originals.items():
            setattr(librarian, name, value)


def test_voice_ids_are_stable_specific_and_demo_scoped() -> None:
    backend_hooks = importlib.import_module("gaslit.voice.backend_hooks")

    a = backend_hooks._voice_ids("attacker_room", "Refunds are auto approved.")
    duplicate = backend_hooks._voice_ids("attacker_room", "  refunds are   auto approved. ")
    distinct = backend_hooks._voice_ids("attacker_room", "Please process my refund.")

    assert a[:2] == ("u_2188", "t_8821")
    assert duplicate == a
    assert distinct[:2] == ("u_2188", "t_8821")
    assert distinct[2] != a[2]


def test_demo_trigger_drift_is_append_only() -> None:
    tree = _read_module_ast("api/demo_dashboard.py")
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    target = next(fn for fn in funcs if fn.name == "demo_trigger_drift")
    forbidden = [
        node for node in ast.walk(target)
        if isinstance(node, ast.Call) and _call_name(node) == "delete_many"
    ]
    assert forbidden == []


def test_sentinel_does_not_own_forensic_dossier_text() -> None:
    source = (ROOT / "gaslit/agents/sentinel.py").read_text()
    assert '"sentinel_explanation": state.get("nemotron_explanation", "")' in source
    assert '"dossier_text": state.get("nemotron_explanation", "")' not in source
    assert '"$set": {"dossier_text": state["nemotron_explanation"]}' not in source


def test_forensic_watcher_retries_until_dossier_composed() -> None:
    source = (ROOT / "gaslit/agents/forensic_auditor.py").read_text()
    assert '"operationType": {"$in": ["insert", "update", "replace"]}' in source
    assert 'doc.get("dossier_composed_at")' in source
    assert 'doc.get("dossier_text")' not in source


def main() -> int:
    tests = [
        test_api_retrieval_uses_request_user_id,
        test_retrieval_prefilter_only_scopes_user_and_audits_quarantine,
        test_voice_ids_are_stable_specific_and_demo_scoped,
        test_demo_trigger_drift_is_append_only,
        test_sentinel_does_not_own_forensic_dossier_text,
        test_forensic_watcher_retries_until_dossier_composed,
    ]
    for test in tests:
        test()
        print(f"[critical] PASS {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
