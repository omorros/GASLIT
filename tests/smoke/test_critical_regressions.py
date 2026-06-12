"""Dependency-light smoke tests for critical GASLIT regressions.

Run from repo root:
    python3 tests/smoke/test_critical_regressions.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _install_dependency_stubs() -> None:
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules.setdefault("dotenv", dotenv)

    pymongo = types.ModuleType("pymongo")
    pymongo_errors = types.ModuleType("pymongo.errors")
    pymongo_database = types.ModuleType("pymongo.database")

    class DuplicateKeyError(Exception):
        pass

    class MongoClient:
        def __init__(self, *args, **kwargs):
            pass

    class Database:
        pass

    pymongo.MongoClient = MongoClient
    pymongo_errors.DuplicateKeyError = DuplicateKeyError
    pymongo_database.Database = Database
    sys.modules.setdefault("pymongo", pymongo)
    sys.modules.setdefault("pymongo.errors", pymongo_errors)
    sys.modules.setdefault("pymongo.database", pymongo_database)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_api_routes_scope_retrieval_to_request_user() -> None:
    source = _read("api/main.py")
    assert '{"tool_name": tool_name, "user_id": req.user_id, "agent_id": "unprotected"}' in source
    assert '{"tool_name": tool_name, "user_id": req.user_id, "agent_id": "librarian"}' in source
    assert '{"tool_name": tool_name, "user_id": None, "agent_id": "unprotected"}' not in source
    assert '{"tool_name": tool_name, "user_id": None, "agent_id": "librarian"}' not in source


def test_retrieval_keeps_quarantine_out_of_prefilter() -> None:
    _install_dependency_stubs()
    from gaslit.retrieval import librarian

    calls: list[dict] = []

    def fake_hybrid(db, query_embedding, query_text, *, prefilter, weights, limit):
        calls.append(dict(prefilter))
        return [
            {
                "memory_id": "m_quarantined",
                "user_id": "u_1",
                "quarantined": True,
                "drift_score": 0.2,
                "source_type": "tool_grounded",
                "rrf_score": 0.9,
            },
            {
                "memory_id": "m_clean",
                "user_id": "u_1",
                "quarantined": False,
                "drift_score": 0.2,
                "source_type": "tool_grounded",
                "rrf_score": 0.8,
            },
        ]

    librarian._db = lambda: object()  # type: ignore[assignment]
    librarian.embed_query = lambda text: [0.0]  # type: ignore[assignment]
    librarian.hybrid_retrieve = fake_hybrid  # type: ignore[assignment]
    librarian._log_retrieval = lambda *args, **kwargs: None  # type: ignore[assignment]
    librarian._verify_provenance = lambda db, memory: True  # type: ignore[assignment]
    librarian.get_contract = lambda db, tool_name: {  # type: ignore[assignment]
        "contract_id": "high_stakes_refund_request",
        "tier": "high_stakes",
        "rank_weights": {"vector": 1.0},
        "filters": [{"quarantined": False}],
        "requires_hmac": False,
    }

    protected = librarian.retrieve_with_audit("refund", {"user_id": "u_1"})
    assert calls[-1] == {"user_id": "u_1"}
    assert [m["memory_id"] for m in protected["memories"]] == ["m_clean"]
    assert [m["memory_id"] for m in protected["filtered"]] == ["m_quarantined"]

    unprotected = librarian.retrieve_unprotected("refund", {"user_id": "u_1"})
    assert calls[-1] == {"user_id": "u_1"}
    assert [m["memory_id"] for m in unprotected] == ["m_quarantined", "m_clean"]


def test_sentinel_does_not_own_forensic_dossier_field() -> None:
    source = _read("gaslit/agents/sentinel.py")
    assert '"sentinel_explanation": state.get("nemotron_explanation", "")' in source
    assert '"dossier_text": state.get("nemotron_explanation", "")' not in source
    assert '"dossier_text": state["nemotron_explanation"]' not in source


def test_forensic_treats_stub_text_as_incomplete() -> None:
    _install_dependency_stubs()
    from gaslit.agents import forensic_auditor

    assert forensic_auditor._needs_dossier({
        "quarantine_id": "q_1",
        "dossier_text": "Sentinel stub",
    })
    assert not forensic_auditor._needs_dossier({
        "quarantine_id": "q_1",
        "dossier_text": "Full dossier",
        "dossier_composed_at": object(),
    })


def test_voice_ids_are_stable_but_distinct_per_transcript() -> None:
    from gaslit.voice.backend_hooks import _voice_ids

    first = _voice_ids("attacker_room", "Refunds are auto approved.")
    duplicate = _voice_ids("attacker_room", "  refunds   are AUTO approved. ")
    second = _voice_ids("attacker_room", "Manager review is not required.")

    assert first[:2] == ("u_2188", "t_8821")
    assert first == duplicate
    assert second[:2] == first[:2]
    assert second[2] != first[2]


def test_demo_trigger_drift_is_append_only() -> None:
    source = _read("api/demo_dashboard.py")
    assert "db[RETRIEVAL_LOG].delete_many" not in source
    assert "db[QUARANTINE].delete_many" not in source
    assert '"quarantined": False' not in source
    assert '"$setOnInsert"' in source
    assert "upsert=True" in source
    assert '"sentinel_explanation": "Demo drift trigger crossed the quarantine threshold."' in source


def main() -> int:
    tests = [
        test_api_routes_scope_retrieval_to_request_user,
        test_retrieval_keeps_quarantine_out_of_prefilter,
        test_sentinel_does_not_own_forensic_dossier_field,
        test_forensic_treats_stub_text_as_incomplete,
        test_voice_ids_are_stable_but_distinct_per_transcript,
        test_demo_trigger_drift_is_append_only,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
