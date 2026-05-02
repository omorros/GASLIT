from __future__ import annotations

import os

import pytest
from pymongo import MongoClient

from gaslit.schemas import (
    AGENT_REGISTRY,
    BELIEF_CONTRACTS,
    BELIEF_PROVENANCE,
    MEMORIES,
    PROVENANCE_TEXT_INDEX,
    QUARANTINE,
    RETRIEVAL_LOG,
    TEXT_INDEX,
    VECTOR_INDEX,
)


CORE_COLLECTIONS = {
    MEMORIES,
    BELIEF_PROVENANCE,
    RETRIEVAL_LOG,
    QUARANTINE,
    BELIEF_CONTRACTS,
    AGENT_REGISTRY,
}


def _db():
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        pytest.skip("MONGODB_URI is required for live Atlas readiness")
    return MongoClient(mongodb_uri, appname="gaslit-atlas-readiness-test").gaslit


def test_live_atlas_core_collections_and_indexes_ready() -> None:
    db = _db()

    assert db.client.admin.command("ping")["ok"] == 1.0
    assert CORE_COLLECTIONS.issubset(set(db.list_collection_names()))

    retrieval_log_info = next(db.list_collections(filter={"name": RETRIEVAL_LOG}))
    assert retrieval_log_info.get("type", "collection") == "collection"
    assert "timeseries" not in retrieval_log_info.get("options", {})

    assert db[AGENT_REGISTRY].count_documents({}) == 4
    assert db[BELIEF_CONTRACTS].count_documents({}) >= 3

    assert "memory_id_unique" in db[MEMORIES].index_information()
    assert "ts_ttl_7d" in db[RETRIEVAL_LOG].index_information()
    assert "expires_at_ttl" in db[QUARANTINE].index_information()

    expected_search_indexes = {
        MEMORIES: {VECTOR_INDEX, TEXT_INDEX},
        BELIEF_PROVENANCE: {PROVENANCE_TEXT_INDEX},
    }
    for collection_name, expected_names in expected_search_indexes.items():
        indexes = {
            index["name"]: index
            for index in db[collection_name].list_search_indexes()
        }
        assert expected_names.issubset(indexes)
        for index_name in expected_names:
            assert indexes[index_name].get("queryable") is True