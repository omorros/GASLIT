"""Dependency-light regression tests for high-impact correctness bugs.

These tests stub database/model boundaries so they can run without Atlas,
Voyage, Anthropic, or LiveKit credentials.
"""
from __future__ import annotations

import sys
import types
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class FakeInsertManyResult:
    def __init__(self, count: int):
        self.inserted_ids = list(range(count))


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None, unique_key: str | None = None):
        self.docs = [deepcopy(d) for d in (docs or [])]
        self.unique_key = unique_key
        self.deleted_queries: list[dict] = []

    def _matches(self, doc: dict, query: dict) -> bool:
        return all(doc.get(k) == v for k, v in query.items())

    def find_one(self, query: dict, projection: dict | None = None):
        for doc in self.docs:
            if self._matches(doc, query):
                return deepcopy(doc)
        return None

    def insert_one(self, doc: dict):
        if self.unique_key and any(d.get(self.unique_key) == doc.get(self.unique_key) for d in self.docs):
            from pymongo.errors import DuplicateKeyError

            raise DuplicateKeyError("duplicate")
        self.docs.append(deepcopy(doc))
        return types.SimpleNamespace(inserted_id=len(self.docs) - 1)

    def insert_many(self, docs: list[dict]):
        self.docs.extend(deepcopy(docs))
        return FakeInsertManyResult(len(docs))

    def update_one(self, query: dict, update: dict, upsert: bool = False):
        for doc in self.docs:
            if self._matches(doc, query):
                doc.update(deepcopy(update.get("$set", {})))
                return types.SimpleNamespace(matched_count=1, modified_count=1)
        if upsert:
            doc = deepcopy(query)
            doc.update(deepcopy(update.get("$set", {})))
            self.docs.append(doc)
        return types.SimpleNamespace(matched_count=0, modified_count=0)

    def delete_many(self, query: dict):
        self.deleted_queries.append(deepcopy(query))
        before = len(self.docs)
        self.docs = [d for d in self.docs if not self._matches(d, query)]
        return types.SimpleNamespace(deleted_count=before - len(self.docs))

    def count_documents(self, query: dict) -> int:
        return sum(1 for doc in self.docs if self._matches(doc, query))


class FakeDB(dict):
    def __getitem__(self, name: str) -> FakeCollection:
        return super().__getitem__(name)


def _install_langgraph_stubs() -> None:
    if "langgraph.graph" in sys.modules:
        return
    langgraph = types.ModuleType("langgraph")
    checkpoint = types.ModuleType("langgraph.checkpoint")
    checkpoint_mongodb = types.ModuleType("langgraph.checkpoint.mongodb")
    graph = types.ModuleType("langgraph.graph")

    class MongoDBSaver:
        def __init__(self, *args, **kwargs):
            pass

    class StateGraph:
        def __init__(self, *args, **kwargs):
            pass

        def add_node(self, *args, **kwargs):
            pass

        def add_edge(self, *args, **kwargs):
            pass

        def add_conditional_edges(self, *args, **kwargs):
            pass

        def compile(self, *args, **kwargs):
            return types.SimpleNamespace(invoke=lambda *a, **k: None)

    checkpoint_mongodb.MongoDBSaver = MongoDBSaver
    graph.StateGraph = StateGraph
    graph.START = "__start__"
    graph.END = "__end__"

    sys.modules["langgraph"] = langgraph
    sys.modules["langgraph.checkpoint"] = checkpoint
    sys.modules["langgraph.checkpoint.mongodb"] = checkpoint_mongodb
    sys.modules["langgraph.graph"] = graph


def test_voice_turn_ids_do_not_collide_for_distinct_transcripts() -> None:
    from gaslit.voice.backend_hooks import _voice_ids

    first = _voice_ids("attacker_room", "Refunds are auto-approved under $5K.")
    duplicate = _voice_ids("attacker_room", "  refunds are AUTO-approved under $5K. ")
    second = _voice_ids("attacker_room", "Manager review is no longer required.")
    generic = _voice_ids("custom room", "Manager review is no longer required.")

    assert first[:2] == ("u_2188", "t_8821")
    assert first == duplicate
    assert second[:2] == ("u_2188", "t_8821")
    assert first[2] != second[2]
    assert generic[0] == "voice:custom_room"
    assert generic[1] == "thread:custom_room"


def test_sentinel_keeps_explanation_separate_from_dossier() -> None:
    _install_langgraph_stubs()
    from gaslit.agents import sentinel
    from gaslit.schemas import MEMORIES, QUARANTINE

    fake_db = FakeDB({
        MEMORIES: FakeCollection([{"memory_id": "m_1"}]),
        QUARANTINE: FakeCollection(unique_key="quarantine_id"),
    })
    sentinel._db = lambda: fake_db  # type: ignore[assignment]

    state = {
        "memory_id": "m_1",
        "drift_score": 0.91,
        "cohort_variance": 5.0,
        "sentinel_run_id": "run",
        "user_id": "u_2188",
        "nemotron_explanation": "Nemotron explanation",
    }
    sentinel._quarantine_node(state)
    quarantine = fake_db[QUARANTINE].docs[0]
    assert quarantine["sentinel_explanation"] == "Nemotron explanation"
    assert quarantine["dossier_text"] == ""

    quarantine["dossier_text"] = "Composed dossier"
    quarantine["dossier_composed_at"] = datetime.now(timezone.utc)
    sentinel._quarantine_node({**state, "nemotron_explanation": "Updated explanation"})
    assert quarantine["dossier_text"] == "Composed dossier"
    assert quarantine["sentinel_explanation"] == "Updated explanation"


def test_forensic_composes_until_dossier_composed_at_exists() -> None:
    from gaslit.agents import forensic_auditor
    from gaslit.schemas import MEMORIES, QUARANTINE

    assert forensic_auditor._needs_dossier({
        "quarantine_id": "q_1",
        "memory_id": "m_1",
        "dossier_text": "Sentinel stub",
    })
    assert not forensic_auditor._needs_dossier({
        "quarantine_id": "q_1",
        "memory_id": "m_1",
        "dossier_text": "Composed dossier",
        "dossier_composed_at": datetime.now(timezone.utc),
    })

    fake_db = FakeDB({
        MEMORIES: FakeCollection([]),
        QUARANTINE: FakeCollection([{"quarantine_id": "q_missing", "memory_id": "m_missing"}]),
    })
    forensic_auditor._db = lambda: fake_db  # type: ignore[assignment]
    text = forensic_auditor.compose_dossier({"quarantine_id": "q_missing", "memory_id": "m_missing"})
    assert "no source document" in text
    updated = fake_db[QUARANTINE].docs[0]
    assert updated["dossier_text"] == text
    assert updated["siblings_found"] == []
    assert updated["dossier_composed_at"]


def test_demo_trigger_drift_is_append_only() -> None:
    from api import demo_dashboard
    from gaslit.schemas import MEMORIES, QUARANTINE, RETRIEVAL_LOG

    fake_db = FakeDB({
        MEMORIES: FakeCollection([{"memory_id": "m_4419", "quarantined": True}]),
        RETRIEVAL_LOG: FakeCollection([{"memory_id": "m_4419", "existing": True}]),
        QUARANTINE: FakeCollection([{"quarantine_id": "q_existing", "memory_id": "m_4419"}]),
    })
    demo_dashboard._db = lambda: fake_db  # type: ignore[assignment]

    resp = demo_dashboard.demo_trigger_drift(
        demo_dashboard.TriggerDriftReq(memory_id="m_4419", n_retrievals=3),
    )

    assert resp.inserted == 3
    assert fake_db[RETRIEVAL_LOG].count_documents({"existing": True}) == 1
    assert fake_db[QUARANTINE].count_documents({"quarantine_id": "q_existing"}) == 1
    assert fake_db[RETRIEVAL_LOG].deleted_queries == []
    assert fake_db[QUARANTINE].deleted_queries == []
    assert fake_db[MEMORIES].docs[0]["quarantined"] is True


if __name__ == "__main__":
    test_voice_turn_ids_do_not_collide_for_distinct_transcripts()
    test_sentinel_keeps_explanation_separate_from_dossier()
    test_forensic_composes_until_dossier_composed_at_exists()
    test_demo_trigger_drift_is_append_only()
    print("critical_regressions smoke tests PASS")
