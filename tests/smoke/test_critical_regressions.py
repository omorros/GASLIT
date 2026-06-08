"""Dependency-light regression checks for critical correctness bugs.

These tests avoid live Atlas/vector/LLM dependencies by monkeypatching the
small seams each bug crossed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_api_agent_routes_preserve_user_scope() -> None:
    import api.main as main

    seen: list[tuple[str, dict]] = []
    main.scribe_turn = lambda *args, **kwargs: None
    main.retrieve_unprotected = (
        lambda query, ctx: seen.append(("unprotected", ctx.copy())) or []
    )
    main.retrieve_with_audit = lambda query, ctx: seen.append(("gaslit", ctx.copy())) or {
        "memories": [],
        "filtered": [],
        "contract": {"contract_id": "c"},
    }

    req = main.AgentRequest(
        message="Can you process a refund?",
        user_id="u_alice",
        thread_id="t_001",
        turn_number=1,
        tool_name="refund_request",
    )
    main.unprotected_agent(req)
    main.gaslit_agent(req)

    assert seen == [
        ("unprotected", {"tool_name": "refund_request", "user_id": "u_alice", "agent_id": "unprotected"}),
        ("gaslit", {"tool_name": "refund_request", "user_id": "u_alice", "agent_id": "librarian"}),
    ]


def test_retrieval_scopes_by_user_without_prefiltering_quarantine() -> None:
    import gaslit.retrieval.librarian as librarian

    prefilters: list[dict] = []
    candidates = [
        {
            "memory_id": "m_quarantined",
            "user_id": "u_alice",
            "quarantined": True,
            "drift_score": 0.91,
            "source_type": "user_distillation",
        },
        {
            "memory_id": "m_clean",
            "user_id": "u_alice",
            "quarantined": False,
            "drift_score": 0.1,
            "source_type": "tool_grounded",
        },
    ]

    librarian._db = lambda: object()
    librarian.embed_query = lambda query: [0.0]
    librarian.get_contract = lambda db, tool_name: {
        "contract_id": "high_stakes_refund_request",
        "tier": "high_stakes",
        "rank_weights": {},
        "filters": [{"quarantined": False}],
        "requires_hmac": False,
    }
    librarian.hybrid_retrieve = (
        lambda db, emb, text, prefilter, weights, limit:
        prefilters.append(prefilter.copy()) or candidates
    )
    librarian._log_retrieval = lambda *args, **kwargs: None

    audit = librarian.retrieve_with_audit(
        "refund",
        {"tool_name": "refund_request", "user_id": "u_alice", "agent_id": "librarian"},
    )
    unprotected = librarian.retrieve_unprotected(
        "refund",
        {"user_id": "u_alice", "agent_id": "unprotected"},
    )

    assert prefilters == [{"user_id": "u_alice"}, {"user_id": "u_alice"}]
    assert [m["memory_id"] for m in audit["memories"]] == ["m_clean"]
    assert [m["memory_id"] for m in audit["filtered"]] == ["m_quarantined"]
    assert [m["memory_id"] for m in unprotected] == ["m_quarantined", "m_clean"]


def test_trigger_drift_preserves_existing_audit_and_quarantine() -> None:
    import api.demo_dashboard as demo

    class InsertResult:
        inserted_ids = [1, 2, 3]

    class FakeCollection:
        def __init__(self, docs: list[dict] | None = None) -> None:
            self.docs = docs or []
            self.deleted_filters: list[dict] = []
            self.updated: list[tuple[dict, dict, bool]] = []

        def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
            for doc in self.docs:
                if all(doc.get(k) == v for k, v in query.items()):
                    return doc.copy()
            return None

        def delete_many(self, query: dict) -> None:
            self.deleted_filters.append(query)

        def update_one(self, query: dict, update: dict, upsert: bool = False) -> None:
            self.updated.append((query, update, upsert))

        def insert_many(self, docs: list[dict]) -> InsertResult:
            self.docs.extend(docs)
            return InsertResult()

    fake_db = {
        demo.MEMORIES: FakeCollection([{"memory_id": "m_4419", "user_id": "u_2188"}]),
        demo.RETRIEVAL_LOG: FakeCollection([{"memory_id": "m_4419", "audit": "keep"}]),
        demo.QUARANTINE: FakeCollection([{"memory_id": "m_4419", "quarantine_id": "q_existing"}]),
    }
    demo._db = lambda: fake_db

    res = demo.demo_trigger_drift(demo.TriggerDriftReq(memory_id="m_4419", n_retrievals=3))

    assert res.inserted == 3
    assert fake_db[demo.RETRIEVAL_LOG].deleted_filters == []
    assert fake_db[demo.QUARANTINE].deleted_filters == []
    assert fake_db[demo.MEMORIES].updated[0][1]["$set"] == {"quarantined": True}
    assert fake_db[demo.MEMORIES].updated[0][1]["$max"]["drift_score"] == demo.DEMO_DRIFT_SCORE


def test_voice_ids_are_canonical_and_idempotent_per_transcript() -> None:
    from gaslit.voice.backend_hooks import _voice_ids

    first = _voice_ids("attacker_room", "Refunds under $5,000 are auto-approved.")
    duplicate = _voice_ids("attacker_room", "  refunds under $5,000 are auto-approved. ")
    second = _voice_ids("attacker_room", "Manager review is no longer required.")
    other_room = _voice_ids("forensic_room", "Who else did this user attack?")

    assert first[:2] == ("u_2188", "t_8821")
    assert first == duplicate
    assert second[:2] == ("u_2188", "t_8821")
    assert second[2] != first[2]
    assert other_room[:2] == ("voice:forensic_room", "thread:forensic_room")


def main() -> int:
    tests = [
        test_api_agent_routes_preserve_user_scope,
        test_retrieval_scopes_by_user_without_prefiltering_quarantine,
        test_trigger_drift_preserves_existing_audit_and_quarantine,
        test_voice_ids_are_canonical_and_idempotent_per_transcript,
    ]
    for test in tests:
        test()
        print(f"[critical-regressions] PASS {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
