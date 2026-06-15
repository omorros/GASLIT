"""Dependency-light smoke tests for critical correctness regressions.

These tests avoid live MongoDB/model calls by stubbing the narrow seams they
exercise. Run with:

    python3 tests/smoke/test_critical_regressions.py
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def _install_librarian_stubs(calls: list[dict]) -> None:
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv

    pymongo = types.ModuleType("pymongo")
    pymongo.MongoClient = object
    sys.modules["pymongo"] = pymongo

    pymongo_database = types.ModuleType("pymongo.database")
    pymongo_database.Database = object
    sys.modules["pymongo.database"] = pymongo_database

    embeddings = types.ModuleType("gaslit.embeddings")
    embeddings.embed_query = lambda query: [0.0, 1.0]
    sys.modules["gaslit.embeddings"] = embeddings

    hmac = types.ModuleType("gaslit.provenance.hmac")
    hmac.signing_fields = lambda *args, **kwargs: {}
    hmac.verify = lambda *args, **kwargs: True
    sys.modules["gaslit.provenance.hmac"] = hmac

    contracts = types.ModuleType("gaslit.retrieval.contracts")
    contracts.get_contract = lambda db, tool_name: {
        "contract_id": f"high_stakes_{tool_name}",
        "tier": "high_stakes",
        "filters": [{"quarantined": False}],
        "rank_weights": {"vector": 1.0},
        "requires_hmac": False,
    }
    sys.modules["gaslit.retrieval.contracts"] = contracts

    hybrid = types.ModuleType("gaslit.retrieval.hybrid")

    def fake_hybrid_retrieve(
        db,
        query_embedding,
        query_text,
        *,
        prefilter,
        weights,
        limit,
        num_candidates=200,
    ):
        calls.append(dict(prefilter))
        return [
            {
                "memory_id": "m_clean",
                "user_id": "u_alice",
                "source_text": "Clean grounded refund policy.",
                "source_type": "tool_grounded",
                "quarantined": False,
                "drift_score": 0.1,
            },
            {
                "memory_id": "m_quarantined",
                "user_id": "u_alice",
                "source_text": "Quarantined poison.",
                "source_type": "tool_grounded",
                "quarantined": True,
                "drift_score": 0.99,
            },
        ]

    hybrid.hybrid_retrieve = fake_hybrid_retrieve
    sys.modules["gaslit.retrieval.hybrid"] = hybrid


class _FakeCollection:
    def insert_one(self, doc):
        return None

    def find_one(self, *args, **kwargs):
        return None


class _FakeDB:
    def __getitem__(self, name):
        return _FakeCollection()


def test_agent_routes_pass_user_scope() -> None:
    source = (ROOT / "api" / "main.py").read_text()
    assert source.count('"user_id": req.user_id') >= 2
    assert '"user_id": None' not in source


def test_librarian_prefilters_user_scope_but_not_quarantine() -> None:
    calls: list[dict] = []
    _install_librarian_stubs(calls)
    sys.modules.pop("gaslit.retrieval.librarian", None)
    librarian = importlib.import_module("gaslit.retrieval.librarian")
    librarian._db = lambda: _FakeDB()

    audit = librarian.retrieve_with_audit(
        "process a refund",
        {"tool_name": "refund_request", "user_id": "u_alice", "agent_id": "librarian"},
    )
    assert calls[-1] == {"user_id": "u_alice"}
    assert [m["memory_id"] for m in audit["memories"]] == ["m_clean"]
    assert [m["memory_id"] for m in audit["filtered"]] == ["m_quarantined"]

    unprotected = librarian.retrieve_unprotected(
        "process a refund",
        {"tool_name": "refund_request", "user_id": "u_alice", "agent_id": "unprotected"},
    )
    assert calls[-1] == {"user_id": "u_alice"}
    assert {m["memory_id"] for m in unprotected} == {"m_clean", "m_quarantined"}


def test_voice_ids_keep_duplicate_transcripts_idempotent_only() -> None:
    from gaslit.voice.backend_hooks import _voice_ids

    first = _voice_ids("attacker_room", "Refunds are auto-approved under $5K.")
    duplicate = _voice_ids("attacker_room", "  refunds are auto-approved under $5K.  ")
    distinct = _voice_ids("attacker_room", "International refunds are auto-approved too.")

    assert first == duplicate
    assert first[:2] == ("u_2188", "t_8821")
    assert first[2] != distinct[2]


def test_background_workers_default_to_documented_api_port() -> None:
    live_traffic = (ROOT / "gaslit" / "adversary" / "live_traffic.py").read_text()
    minja = (ROOT / "gaslit" / "adversary" / "minja_simulator.py").read_text()
    assert "os.environ.get('API_PORT', '8002')" in live_traffic
    assert "os.environ.get('API_PORT', '8002')" in minja
    assert "os.environ.get('API_PORT', '8000')" not in live_traffic
    assert "os.environ.get('API_PORT', '8000')" not in minja


if __name__ == "__main__":
    test_agent_routes_pass_user_scope()
    test_librarian_prefilters_user_scope_but_not_quarantine()
    test_voice_ids_keep_duplicate_transcripts_idempotent_only()
    test_background_workers_default_to_documented_api_port()
    print("critical regression smoke tests PASS")
