"""Dependency-light regression checks for critical demo correctness bugs.

These tests use in-memory collection fakes so they can run without Atlas, model
credentials, or a live FastAPI server.
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from api import demo_dashboard
from gaslit.agents import forensic_auditor
from gaslit.retrieval import librarian
from gaslit.schemas import MEMORIES, QUARANTINE, RETRIEVAL_LOG


class InsertManyResult:
    def __init__(self, n: int) -> None:
        self.inserted_ids = list(range(n))


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs = list(docs or [])
        self.deleted_queries: list[dict] = []

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                if not projection:
                    return dict(doc)
                if any(v == 0 for v in projection.values()):
                    return {k: v for k, v in doc.items() if projection.get(k, 1) != 0}
                return {k: doc[k] for k, v in projection.items() if v and k in doc}
        return None

    def insert_many(self, docs: list[dict]) -> InsertManyResult:
        self.docs.extend(dict(doc) for doc in docs)
        return InsertManyResult(len(docs))

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> None:
        doc = self.find_one(query)
        if doc is None:
            if not upsert:
                return
            doc = dict(query)
            self.docs.append(doc)

        if "$setOnInsert" in update and all(item in query.items() for item in doc.items()):
            doc.update(update["$setOnInsert"])
        if "$set" in update:
            doc.update(update["$set"])
        if "$inc" in update:
            for key, value in update["$inc"].items():
                doc[key] = doc.get(key, 0) + value

        for idx, existing in enumerate(self.docs):
            if all(existing.get(k) == v for k, v in query.items()):
                self.docs[idx] = doc
                return

    def delete_many(self, query: dict) -> None:
        self.deleted_queries.append(query)
        self.docs = [
            doc for doc in self.docs
            if not all(doc.get(k) == v for k, v in query.items())
        ]


class FakeDB(dict):
    def __getitem__(self, name: str) -> FakeCollection:
        return super().__getitem__(name)


def test_trigger_drift_is_append_only_and_idempotent() -> None:
    db = FakeDB({
        MEMORIES: FakeCollection([{
            "memory_id": "m_4419",
            "user_id": "u_2188",
            "source_text": "poisoned refund policy",
            "retrieval_count": 5,
            "quarantined": False,
        }]),
        RETRIEVAL_LOG: FakeCollection([{
            "memory_id": "m_4419",
            "agent_id": "librarian",
            "retrieved_rank": 1,
            "existing": True,
        }]),
        QUARANTINE: FakeCollection([{
            "quarantine_id": "q_existing",
            "memory_id": "m_4419",
            "dossier_text": "real audit evidence",
        }]),
    })
    original_db = demo_dashboard._db
    demo_dashboard._db = lambda: db
    try:
        first = demo_dashboard.demo_trigger_drift(
            demo_dashboard.TriggerDriftReq(memory_id="m_4419", n_retrievals=3),
        )
        second = demo_dashboard.demo_trigger_drift(
            demo_dashboard.TriggerDriftReq(memory_id="m_4419", n_retrievals=2),
        )
    finally:
        demo_dashboard._db = original_db

    assert first.inserted == 3
    assert second.inserted == 2
    assert db[RETRIEVAL_LOG].deleted_queries == []
    assert db[QUARANTINE].deleted_queries == []
    assert any(doc.get("existing") for doc in db[RETRIEVAL_LOG].docs)
    assert any(doc.get("quarantine_id") == "q_existing" for doc in db[QUARANTINE].docs)
    assert sum(1 for doc in db[QUARANTINE].docs if doc.get("quarantine_id") == "q_demo_m_4419") == 1

    memory = db[MEMORIES].find_one({"memory_id": "m_4419"})
    assert memory is not None
    assert memory["quarantined"] is True
    assert memory["retrieval_count"] == 10


def test_librarian_scopes_by_user_without_prefiltering_quarantine() -> None:
    calls: list[dict] = []
    candidate = {
        "memory_id": "m_4419",
        "user_id": "u_2188",
        "quarantined": True,
        "source_type": "user_distillation",
        "drift_score": 0.9,
    }

    def fake_hybrid(_db, _embedding, _query, *, prefilter, weights, limit):
        calls.append({"prefilter": prefilter, "weights": weights, "limit": limit})
        return [candidate]

    original_db = librarian._db
    original_embed = librarian.embed_query
    original_contract = librarian.get_contract
    original_hybrid = librarian.hybrid_retrieve
    original_log = librarian._log_retrieval
    original_verify = librarian._verify_provenance
    librarian._db = lambda: object()
    librarian.embed_query = lambda _query: [0.1]
    librarian.get_contract = lambda _db, _tool: {
        "contract_id": "high_stakes_refund",
        "tier": "high_stakes",
        "rank_weights": {"vector": 1.0},
        "filters": [{"quarantined": {"$ne": True}}],
        "requires_hmac": False,
    }
    librarian.hybrid_retrieve = fake_hybrid
    librarian._log_retrieval = lambda *_args, **_kwargs: None
    librarian._verify_provenance = lambda *_args, **_kwargs: True
    try:
        audit = librarian.retrieve_with_audit(
            "refund",
            {"tool_name": "refund_request", "user_id": "u_2188", "agent_id": "librarian"},
        )
        unprotected = librarian.retrieve_unprotected(
            "refund",
            {"tool_name": "refund_request", "user_id": "u_2188", "agent_id": "unprotected"},
        )
    finally:
        librarian._db = original_db
        librarian.embed_query = original_embed
        librarian.get_contract = original_contract
        librarian.hybrid_retrieve = original_hybrid
        librarian._log_retrieval = original_log
        librarian._verify_provenance = original_verify

    assert calls[0]["prefilter"] == {"user_id": "u_2188"}
    assert calls[1]["prefilter"] == {"user_id": "u_2188"}
    assert audit["memories"] == []
    assert audit["filtered"][0]["memory_id"] == "m_4419"
    assert unprotected == [candidate]


def test_forensic_fallback_dossier_is_persisted() -> None:
    db = FakeDB({
        MEMORIES: FakeCollection([]),
        QUARANTINE: FakeCollection([{
            "quarantine_id": "q_missing",
            "memory_id": "m_missing",
            "quarantined_at": "now",
        }]),
    })
    original_db = forensic_auditor._db
    forensic_auditor._db = lambda: db
    try:
        dossier = forensic_auditor.compose_dossier({
            "quarantine_id": "q_missing",
            "memory_id": "m_missing",
            "quarantined_at": "now",
        })
    finally:
        forensic_auditor._db = original_db

    q = db[QUARANTINE].find_one({"quarantine_id": "q_missing"})
    assert dossier == "Memory m_missing quarantined but no source document was found."
    assert q is not None
    assert q["dossier_text"] == dossier
    assert q["siblings_found"] == []
    assert q.get("dossier_composed_at") is not None


if __name__ == "__main__":
    test_trigger_drift_is_append_only_and_idempotent()
    test_librarian_scopes_by_user_without_prefiltering_quarantine()
    test_forensic_fallback_dossier_is_persisted()
    print("[critical] PASS")
