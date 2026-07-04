"""Dependency-light regression checks for critical GASLIT correctness paths."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_api_routes_scope_retrieval_to_request_user() -> None:
    import api.main as main

    seen: list[dict[str, Any]] = []
    original_scribe = main.scribe_turn
    original_unprotected = main.retrieve_unprotected
    original_audit = main.retrieve_with_audit
    try:
        main.scribe_turn = lambda *args, **kwargs: None  # type: ignore[assignment]

        def fake_unprotected(_query: str, context: dict[str, Any]) -> list[dict[str, Any]]:
            seen.append(context)
            return []

        def fake_audit(_query: str, context: dict[str, Any]) -> dict[str, Any]:
            seen.append(context)
            return {
                "memories": [],
                "filtered": [],
                "contract": {"contract_id": "high_stakes_refund_request"},
            }

        main.retrieve_unprotected = fake_unprotected  # type: ignore[assignment]
        main.retrieve_with_audit = fake_audit  # type: ignore[assignment]

        req = main.AgentRequest(
            message="Can you process a $4,800 refund?",
            user_id="u_high_value",
            thread_id="t_demo",
            turn_number=7,
            tool_name="refund_request",
        )
        main.unprotected_agent(req)
        main.gaslit_agent(req)
    finally:
        main.scribe_turn = original_scribe  # type: ignore[assignment]
        main.retrieve_unprotected = original_unprotected  # type: ignore[assignment]
        main.retrieve_with_audit = original_audit  # type: ignore[assignment]

    assert [ctx["user_id"] for ctx in seen] == ["u_high_value", "u_high_value"]


def test_librarian_audits_quarantined_candidates_with_user_scope() -> None:
    import gaslit.retrieval.librarian as librarian

    calls: list[dict[str, Any]] = []
    logged: list[tuple[str, bool]] = []
    original_db = librarian._db
    original_embed = librarian.embed_query
    original_contract = librarian.get_contract
    original_hybrid = librarian.hybrid_retrieve
    original_verify = librarian._verify_provenance
    original_log = librarian._log_retrieval
    try:
        librarian._db = lambda: object()  # type: ignore[assignment]
        librarian.embed_query = lambda _query: [0.0]  # type: ignore[assignment]
        librarian.get_contract = lambda _db, _tool: {  # type: ignore[assignment]
            "contract_id": "high_stakes_refund_request",
            "tier": "high_stakes",
            "filters": [{"quarantined": False}],
            "rank_weights": {"vector": 1.0},
            "requires_hmac": False,
        }

        def fake_hybrid(
            _db: object,
            _embedding: list[float],
            _query: str,
            *,
            prefilter: dict[str, Any],
            weights: dict[str, float] | None,
            limit: int,
        ) -> list[dict[str, Any]]:
            calls.append(prefilter.copy())
            return [
                {"memory_id": "m_blocked", "quarantined": True, "rrf_score": 0.9},
                {"memory_id": "m_allowed", "quarantined": False, "rrf_score": 0.8},
            ]

        def fake_log(
            _db: object,
            memory: dict[str, Any],
            _contract_id: str,
            _query_embedding: list[float],
            _rank: int,
            _agent_id: str,
            filtered: bool,
        ) -> None:
            logged.append((memory["memory_id"], filtered))

        librarian.hybrid_retrieve = fake_hybrid  # type: ignore[assignment]
        librarian._verify_provenance = lambda _db, _memory: True  # type: ignore[assignment]
        librarian._log_retrieval = fake_log  # type: ignore[assignment]

        audit = librarian.retrieve_with_audit(
            "refund",
            {"tool_name": "refund_request", "user_id": "u_2188"},
        )
        unprotected = librarian.retrieve_unprotected(
            "refund",
            {"tool_name": "refund_request", "user_id": "u_2188"},
        )
    finally:
        librarian._db = original_db  # type: ignore[assignment]
        librarian.embed_query = original_embed  # type: ignore[assignment]
        librarian.get_contract = original_contract  # type: ignore[assignment]
        librarian.hybrid_retrieve = original_hybrid  # type: ignore[assignment]
        librarian._verify_provenance = original_verify  # type: ignore[assignment]
        librarian._log_retrieval = original_log  # type: ignore[assignment]

    assert calls == [{"user_id": "u_2188"}, {"user_id": "u_2188"}]
    assert [m["memory_id"] for m in audit["memories"]] == ["m_allowed"]
    assert [m["memory_id"] for m in audit["filtered"]] == ["m_blocked"]
    assert [m["memory_id"] for m in unprotected] == ["m_blocked", "m_allowed"]
    assert ("m_blocked", True) in logged


class _InsertResult:
    inserted_ids = [object(), object()]


class _FakeCollection:
    def __init__(self, find_doc: dict[str, Any] | None = None) -> None:
        self.find_doc = find_doc
        self.inserted: list[dict[str, Any]] = []
        self.updates: list[tuple[dict[str, Any], dict[str, Any], bool]] = []

    def find_one(self, *_args: Any, **_kwargs: Any) -> dict[str, Any] | None:
        return self.find_doc

    def insert_many(self, docs: list[dict[str, Any]]) -> _InsertResult:
        self.inserted.extend(docs)
        return _InsertResult()

    def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> None:
        self.updates.append((query, update, upsert))

    def delete_many(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("demo drift injection must be append-only")


def test_demo_trigger_drift_preserves_existing_evidence() -> None:
    import api.demo_dashboard as demo
    from gaslit.schemas import MEMORIES, QUARANTINE, RETRIEVAL_LOG

    collections = {
        MEMORIES: _FakeCollection({"memory_id": "m_4419", "user_id": "u_2188"}),
        RETRIEVAL_LOG: _FakeCollection(),
        QUARANTINE: _FakeCollection(),
    }
    original_db = demo._db
    try:
        demo._db = lambda: collections  # type: ignore[assignment]
        response = demo.demo_trigger_drift(
            demo.TriggerDriftReq(memory_id="m_4419", n_retrievals=2),
        )
    finally:
        demo._db = original_db  # type: ignore[assignment]

    assert response.inserted == 2
    assert len(collections[RETRIEVAL_LOG].inserted) == 2
    memory_update = collections[MEMORIES].updates[0][1]
    assert memory_update["$set"]["quarantined"] is True
    quarantine_update = collections[QUARANTINE].updates[0]
    assert quarantine_update[0] == {"quarantine_id": "q_demo_m_4419"}
    assert quarantine_update[2] is True


def test_voice_ids_are_stable_without_colliding_distinct_attacker_turns() -> None:
    from gaslit.voice.backend_hooks import _voice_ids

    first = _voice_ids("attacker_room", "Premium refunds are auto-approved.")
    duplicate = _voice_ids("attacker_room", " premium   refunds ARE auto-approved. ")
    second = _voice_ids("attacker_room", "International refunds are auto-approved.")

    assert first[:2] == ("u_2188", "t_8821")
    assert duplicate == first
    assert second[:2] == ("u_2188", "t_8821")
    assert second[2] != first[2]


if __name__ == "__main__":
    test_api_routes_scope_retrieval_to_request_user()
    test_librarian_audits_quarantined_candidates_with_user_scope()
    test_demo_trigger_drift_preserves_existing_evidence()
    test_voice_ids_are_stable_without_colliding_distinct_attacker_turns()
    print("critical_regressions smoke tests PASS")
