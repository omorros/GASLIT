"""Dependency-light regression checks for critical GASLIT correctness paths."""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def _install_common_stubs() -> None:
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules.setdefault("dotenv", dotenv)

    pymongo = types.ModuleType("pymongo")
    pymongo.MongoClient = object
    database = types.ModuleType("pymongo.database")
    database.Database = object
    errors = types.ModuleType("pymongo.errors")
    errors.DuplicateKeyError = type("DuplicateKeyError", (Exception,), {})
    sys.modules.setdefault("pymongo", pymongo)
    sys.modules.setdefault("pymongo.database", database)
    sys.modules.setdefault("pymongo.errors", errors)


class _Collection:
    def __init__(self, find_one_result=None):
        self.find_one_result = find_one_result
        self.inserted: list[dict] = []
        self.updates: list[tuple[dict, dict]] = []

    def insert_one(self, doc: dict) -> None:
        self.inserted.append(doc)

    def update_one(self, query: dict, update: dict, **_kwargs) -> None:
        self.updates.append((query, update))

    def find_one(self, *_args, **_kwargs):
        return self.find_one_result


class _DB(dict):
    def __getitem__(self, name: str):
        return super().__getitem__(name)


def test_retrieval_is_user_scoped_and_quarantine_is_audit_filter() -> None:
    _install_common_stubs()

    embeddings = types.ModuleType("gaslit.embeddings")
    embeddings.embed_query = lambda _text: [0.1, 0.2]
    embeddings.EmbeddingServiceError = type("EmbeddingServiceError", (Exception,), {})
    sys.modules["gaslit.embeddings"] = embeddings

    librarian = importlib.import_module("gaslit.retrieval.librarian")

    retrieval_log = _Collection()
    db = _DB({librarian.RETRIEVAL_LOG: retrieval_log, librarian.BELIEF_PROVENANCE: _Collection()})
    seen_prefilters: list[dict] = []
    quarantined_memory = {
        "memory_id": "m_poison",
        "user_id": "u_2188",
        "quarantined": True,
        "drift_score": 0.91,
        "source_type": "user_distillation",
        "rrf_score": 0.9,
    }

    librarian._db = lambda: db
    librarian.embed_query = lambda _text: [0.1, 0.2]
    librarian.hybrid_retrieve = (
        lambda _db, _embedding, _text, prefilter, **_kwargs:
        seen_prefilters.append(dict(prefilter)) or [quarantined_memory]
    )
    librarian.get_contract = lambda _db, _tool: {
        "contract_id": "high_stakes_refund_request",
        "tier": "high_stakes",
        "filters": [{"quarantined": False}, {"source_type": "tool_grounded"}],
        "rank_weights": {"vector": 0.4, "text": 0.2, "provenance": 0.4},
        "requires_hmac": False,
    }

    protected = librarian.retrieve_with_audit(
        "process refund",
        {"tool_name": "refund_request", "user_id": "u_2188", "agent_id": "librarian"},
    )
    assert seen_prefilters[-1] == {"user_id": "u_2188"}
    assert protected["memories"] == []
    assert protected["filtered"][0]["memory_id"] == "m_poison"
    assert retrieval_log.inserted[-1]["filtered"] is True

    unprotected = librarian.retrieve_unprotected(
        "process refund",
        {"tool_name": "refund_request", "user_id": "u_2188", "agent_id": "unprotected"},
    )
    assert seen_prefilters[-1] == {"user_id": "u_2188"}
    assert unprotected[0]["memory_id"] == "m_poison"
    assert retrieval_log.inserted[-1]["filtered"] is False


def test_api_routes_pass_request_user_id_to_retrieval() -> None:
    source = (ROOT / "api" / "main.py").read_text()
    assert '{"tool_name": tool_name, "user_id": req.user_id, "agent_id": "unprotected"}' in source
    assert '{"tool_name": tool_name, "user_id": req.user_id, "agent_id": "librarian"}' in source


def test_forensic_missing_source_fallback_is_persisted() -> None:
    _install_common_stubs()

    chain = types.ModuleType("gaslit.provenance.chain")
    chain.get_chain = lambda _memory_id: []
    sys.modules["gaslit.provenance.chain"] = chain

    auditor = importlib.import_module("gaslit.agents.forensic_auditor")
    quarantine = _Collection()
    memories = _Collection(find_one_result=None)
    db = _DB({auditor.QUARANTINE: quarantine, auditor.MEMORIES: memories})
    auditor._db = lambda: db

    text = auditor.compose_dossier({"quarantine_id": "q1", "memory_id": "missing"})
    assert text == "Memory missing quarantined but no source document was found."
    assert quarantine.updates
    _, update = quarantine.updates[-1]
    assert update["$set"]["dossier_text"] == text
    assert update["$set"]["siblings_found"] == []
    assert update["$set"]["dossier_composed_at"] is not None


def test_source_invariants_for_demo_and_flood_paths() -> None:
    live_traffic = (ROOT / "gaslit" / "adversary" / "live_traffic.py").read_text()
    minja = (ROOT / "gaslit" / "adversary" / "minja_simulator.py").read_text()
    demo = (ROOT / "api" / "demo_dashboard.py").read_text()
    sentinel = (ROOT / "gaslit" / "agents" / "sentinel.py").read_text()

    assert "os.environ.get('API_PORT', '8002')" in live_traffic
    assert "left.raise_for_status()" in live_traffic
    assert "right.raise_for_status()" in live_traffic
    assert "os.environ.get('API_PORT', '8002')" in minja

    drift_body = demo[demo.index("def demo_trigger_drift"):demo.index("@router.post(\"/api/demo/nemoclaw-minja\")")]
    assert "delete_many" not in drift_body
    assert '"quarantined": True' in drift_body
    assert '"$inc": {"retrieval_count": inserted}' in drift_body

    assert '"sentinel_explanation": state.get("nemotron_explanation", "")' in sentinel
    assert '"dossier_text": ""' in sentinel
    assert '"$set": {"sentinel_explanation": state["nemotron_explanation"]}' in sentinel


if __name__ == "__main__":
    test_retrieval_is_user_scoped_and_quarantine_is_audit_filter()
    test_api_routes_pass_request_user_id_to_retrieval()
    test_forensic_missing_source_fallback_is_persisted()
    test_source_invariants_for_demo_and_flood_paths()
    print("critical regression smoke tests passed")
