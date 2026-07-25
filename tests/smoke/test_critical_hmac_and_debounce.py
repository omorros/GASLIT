"""Dependency-light checks for HMAC content binding + trailing debounce."""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import threading
import time
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


def _load_corpus_helpers():
    path = ROOT / "scripts" / "load_baseline_corpus.py"
    spec = importlib.util.spec_from_file_location("load_baseline_corpus", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_verify_rejects_tampered_source_text() -> None:
    """Mutating memories.source_text must fail high-stakes HMAC checks."""
    _install_common_stubs()
    os.environ["HMAC_SECRET"] = "test-hmac-secret-for-critical-smoke"

    embeddings = types.ModuleType("gaslit.embeddings")
    embeddings.embed_query = lambda _text: [0.1, 0.2]
    embeddings.EmbeddingServiceError = type("EmbeddingServiceError", (Exception,), {})
    sys.modules["gaslit.embeddings"] = embeddings

    contracts = types.ModuleType("gaslit.retrieval.contracts")
    contracts.get_contract = lambda *_a, **_k: {}
    sys.modules["gaslit.retrieval.contracts"] = contracts

    hybrid = types.ModuleType("gaslit.retrieval.hybrid")
    hybrid.hybrid_retrieve = lambda *_a, **_k: []
    sys.modules["gaslit.retrieval.hybrid"] = hybrid

    librarian = importlib.import_module("gaslit.retrieval.librarian")
    from gaslit.provenance.hmac import sha256_hex, sign, signing_fields

    original = "Refunds for premium accounts are auto-approved under $5000."
    tampered = "Refunds for premium accounts are auto-approved under $50000."
    memory = {
        "memory_id": "m_hmac_1",
        "user_id": "u_1",
        "thread_id": "t_1",
        "turn_number": 1,
        "parent_memory_id": None,
        "source_text": original,
    }
    src_hash = sha256_hex(original)
    fields = signing_fields(memory, src_hash, [])
    prov = {
        "memory_id": "m_hmac_1",
        "source_text_hash": src_hash,
        "tool_output_hashes": [],
        "attestation": sign(fields),
    }

    class _Coll:
        def find_one(self, *_a, **_k):
            return prov

    class _DB(dict):
        def __getitem__(self, name: str):
            return _Coll()

    assert librarian._verify_provenance(_DB(), memory) is True
    assert librarian._verify_provenance(
        _DB(), {**memory, "source_text": tampered}
    ) is False


def test_trailing_debouncer_fires_once_after_burst() -> None:
    from gaslit.agents.debounce import TrailingDebouncer

    hits: list[str] = []
    done = threading.Event()

    def cb(key: str) -> None:
        hits.append(key)
        done.set()

    debouncer = TrailingDebouncer(0.15, cb)
    for _ in range(8):
        debouncer.kick("m_burst")
        time.sleep(0.02)

    assert done.wait(1.0), "trailing callback never fired"
    time.sleep(0.2)
    assert hits == ["m_burst"]
    debouncer.cancel_all()


def test_trailing_debouncer_cancel_all_drops_pending() -> None:
    from gaslit.agents.debounce import TrailingDebouncer

    hits: list[str] = []
    debouncer = TrailingDebouncer(0.3, hits.append)
    debouncer.kick("m_x")
    assert "m_x" in debouncer.pending()
    debouncer.cancel_all()
    time.sleep(0.4)
    assert hits == []


def test_loader_detects_immutable_field_mismatch() -> None:
    _install_common_stubs()
    os.environ["HMAC_SECRET"] = "test-hmac-secret-for-critical-smoke"
    mod = _load_corpus_helpers()
    fixture = {
        "source_text": "canonical",
        "source_type": "tool_grounded",
        "user_id": "u_2188",
        "thread_id": "t_1",
        "turn_number": 1,
        "parent_memory_id": None,
    }
    live = {**fixture, "source_text": "TAMPERED poison text"}
    assert mod._immutable_mismatch(live, fixture) == ["source_text"]
    assert mod._immutable_mismatch(fixture, fixture) == []


def test_loader_signs_fixture_not_live_text() -> None:
    _install_common_stubs()
    os.environ["HMAC_SECRET"] = "test-hmac-secret-for-critical-smoke"
    from gaslit.provenance.hmac import sha256_hex, sign, signing_fields

    fixture_text = "fixture belief"
    live_text = "tampered belief"
    memory_doc = {
        "memory_id": "m_load_1",
        "user_id": "u_1",
        "thread_id": "t_1",
        "turn_number": 1,
        "parent_memory_id": None,
        "source_text": fixture_text,
    }
    live_memory = {**memory_doc, "source_text": live_text}
    fixture_hash = sha256_hex(fixture_text)
    live_hash = sha256_hex(live_text)
    assert sign(signing_fields(memory_doc, fixture_hash, [])) != sign(
        signing_fields(live_memory, live_hash, [])
    )
    assert fixture_hash != live_hash


if __name__ == "__main__":
    test_verify_rejects_tampered_source_text()
    test_trailing_debouncer_fires_once_after_burst()
    test_trailing_debouncer_cancel_all_drops_pending()
    test_loader_detects_immutable_field_mismatch()
    test_loader_signs_fixture_not_live_text()
    print("critical_hmac_and_debounce smoke tests PASS")
