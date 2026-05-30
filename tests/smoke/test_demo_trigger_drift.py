"""Smoke tests for the demo drift trigger endpoint.

The endpoint is mounted on the public API, so it must never clear forensic
evidence while generating synthetic retrieval rows for the operator demo.
"""
import sys
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from api import demo_dashboard
from gaslit.schemas import MEMORIES, QUARANTINE, RETRIEVAL_LOG


class _InsertResult:
    def __init__(self, n: int):
        self.inserted_ids = list(range(n))


class _FakeCollection:
    def __init__(self, find_one_result=None):
        self.find_one_result = find_one_result
        self.inserted_docs = []

    def find_one(self, *_args, **_kwargs):
        return self.find_one_result

    def insert_many(self, docs):
        self.inserted_docs.extend(docs)
        return _InsertResult(len(docs))

    def delete_many(self, *_args, **_kwargs):
        raise AssertionError("demo drift trigger must not delete stored evidence")

    def update_one(self, *_args, **_kwargs):
        raise AssertionError("demo drift trigger must not reset memory quarantine state")


class _FakeDB:
    def __init__(self):
        self.collections = {
            MEMORIES: _FakeCollection(find_one_result={"_id": "memory-doc"}),
            RETRIEVAL_LOG: _FakeCollection(),
            QUARANTINE: _FakeCollection(),
        }

    def __getitem__(self, name):
        return self.collections[name]


def test_trigger_drift_appends_without_destroying_evidence():
    fake_db = _FakeDB()
    original_db = demo_dashboard._db
    demo_dashboard._db = lambda: fake_db
    try:
        resp = demo_dashboard.demo_trigger_drift(
            demo_dashboard.TriggerDriftReq(memory_id="m_live", n_retrievals=3),
        )
    finally:
        demo_dashboard._db = original_db

    inserted = fake_db[RETRIEVAL_LOG].inserted_docs
    assert resp.inserted == 3
    assert len(inserted) == 3
    assert {doc["memory_id"] for doc in inserted} == {"m_live"}
    assert all(len(doc["query_embedding"]) == 1024 for doc in inserted)


def test_trigger_drift_rejects_unbounded_request_sizes():
    try:
        demo_dashboard.TriggerDriftReq(n_retrievals=201)
    except ValidationError:
        return
    raise AssertionError("n_retrievals above the endpoint cap should be rejected")


if __name__ == "__main__":
    test_trigger_drift_appends_without_destroying_evidence()
    test_trigger_drift_rejects_unbounded_request_sizes()
    print("demo_trigger_drift smoke tests PASS")
