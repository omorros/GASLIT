"""Regression checks for cross-user retrieval and voice transcript idempotency.

These tests use only the standard library so they can run in minimal CI images.
"""
from __future__ import annotations

import asyncio
import importlib
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def _install_api_fakes(calls: dict[str, list[dict]]) -> None:
    class FakeFastAPI:
        def __init__(self, *args, **kwargs):
            pass

        def add_middleware(self, *args, **kwargs):
            pass

        def include_router(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            return lambda fn: fn

        def post(self, *args, **kwargs):
            return lambda fn: fn

        def on_event(self, *args, **kwargs):
            return lambda fn: fn

    class FakeBaseModel:
        pass

    class FakeMongoClient:
        def __init__(self, *args, **kwargs):
            pass

        def __getitem__(self, name):
            return {}

    def field(default=None, **kwargs):
        return default

    def query(default, **kwargs):
        return default

    fastapi = types.ModuleType("fastapi")
    fastapi.__path__ = []
    fastapi.FastAPI = FakeFastAPI
    fastapi.HTTPException = Exception
    fastapi.Query = query
    middleware = types.ModuleType("fastapi.middleware")
    middleware.__path__ = []
    cors = types.ModuleType("fastapi.middleware.cors")
    cors.CORSMiddleware = object

    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = FakeBaseModel
    pydantic.Field = field

    pymongo = types.ModuleType("pymongo")
    pymongo.MongoClient = FakeMongoClient

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None

    scribe = types.ModuleType("gaslit.agents.scribe")
    scribe.scribe_turn = lambda *args, **kwargs: None

    embeddings = types.ModuleType("gaslit.embeddings")
    embeddings.EmbeddingServiceError = RuntimeError

    librarian = types.ModuleType("gaslit.retrieval.librarian")

    def retrieve_unprotected(message, context):
        calls["unprotected"].append(context)
        return []

    def retrieve_with_audit(message, context):
        calls["gaslit"].append(context)
        return {"memories": [], "filtered": [], "contract": {"contract_id": "c"}}

    librarian.retrieve_unprotected = retrieve_unprotected
    librarian.retrieve_with_audit = retrieve_with_audit

    contracts = types.ModuleType("gaslit.retrieval.contracts")
    contracts.seed_demo_contracts = lambda db: None

    schemas = types.ModuleType("gaslit.schemas")
    schemas.MEMORIES = "memories"
    schemas.QUARANTINE = "quarantine"
    schemas.RETRIEVAL_LOG = "retrieval_log"
    schemas.DB_NAME = "gaslit"
    schemas.bootstrap_collections = lambda db: None
    schemas.seed_agent_registry = lambda db: None

    sys.modules.update(
        {
            "fastapi": fastapi,
            "fastapi.middleware": middleware,
            "fastapi.middleware.cors": cors,
            "pydantic": pydantic,
            "pymongo": pymongo,
            "dotenv": dotenv,
            "gaslit.agents.scribe": scribe,
            "gaslit.embeddings": embeddings,
            "gaslit.retrieval.librarian": librarian,
            "gaslit.retrieval.contracts": contracts,
            "gaslit.schemas": schemas,
        }
    )


def test_agent_routes_scope_retrieval_to_request_user() -> None:
    calls: dict[str, list[dict]] = {"unprotected": [], "gaslit": []}
    _install_api_fakes(calls)
    sys.modules.pop("api.main", None)
    main = importlib.import_module("api.main")

    req = types.SimpleNamespace(
        message="Can you process a $4,800 refund?",
        user_id="u_alice",
        thread_id="t_refund",
        turn_number=1,
        tool_name="refund_request",
    )

    main.unprotected_agent(req)
    main.gaslit_agent(req)

    assert calls["unprotected"][0]["user_id"] == "u_alice"
    assert calls["gaslit"][0]["user_id"] == "u_alice"


def test_voice_transcripts_in_same_room_get_distinct_turns() -> None:
    captured: list[tuple[str, str, int, str]] = []

    fake_scribe = types.ModuleType("gaslit.agents.scribe")

    def scribe_turn(user_id, thread_id, turn_number, transcript):
        captured.append((user_id, thread_id, turn_number, transcript))
        return {"memory_id": f"m_{turn_number}"}

    fake_scribe.scribe_turn = scribe_turn
    sys.modules["gaslit.agents.scribe"] = fake_scribe

    from gaslit.voice.backend_hooks import on_voice_transcript

    async def run() -> None:
        await on_voice_transcript("first poisoned instruction", "attacker_room", "livekit")
        await on_voice_transcript("second poisoned instruction", "attacker_room", "livekit")
        await on_voice_transcript("  First   poisoned instruction ", "attacker_room", "livekit")

    asyncio.run(run())

    assert captured[0][0:2] == ("voice:attacker_room", "thread:attacker_room")
    assert captured[0][2] != captured[1][2]
    assert captured[0][2] == captured[2][2]


def main() -> int:
    test_agent_routes_scope_retrieval_to_request_user()
    test_voice_transcripts_in_same_room_get_distinct_turns()
    print("isolation regression tests PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
