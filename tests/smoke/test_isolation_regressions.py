"""Dependency-free regression tests for recent isolation/data-loss fixes.

Run with:
  python3 tests/smoke/test_isolation_regressions.py
"""
from __future__ import annotations

import asyncio
import importlib
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def _install_api_import_stubs() -> types.ModuleType:
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv

    fastapi = types.ModuleType("fastapi")

    class FastAPI:
        def __init__(self, *args, **kwargs):
            pass

        def add_middleware(self, *args, **kwargs):
            pass

        def on_event(self, *args, **kwargs):
            return lambda fn: fn

        def get(self, *args, **kwargs):
            return lambda fn: fn

        def post(self, *args, **kwargs):
            return lambda fn: fn

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    fastapi.FastAPI = FastAPI
    fastapi.HTTPException = HTTPException
    fastapi.Query = lambda default, **kwargs: default
    sys.modules["fastapi"] = fastapi

    middleware = types.ModuleType("fastapi.middleware")
    cors = types.ModuleType("fastapi.middleware.cors")
    cors.CORSMiddleware = object
    sys.modules["fastapi.middleware"] = middleware
    sys.modules["fastapi.middleware.cors"] = cors

    pydantic = types.ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def Field(default=None, *, default_factory=None, **kwargs):
        return default_factory() if default_factory is not None else default

    pydantic.BaseModel = BaseModel
    pydantic.Field = Field
    sys.modules["pydantic"] = pydantic

    pymongo = types.ModuleType("pymongo")
    pymongo.MongoClient = object
    sys.modules["pymongo"] = pymongo

    scribe = types.ModuleType("gaslit.agents.scribe")
    scribe.scribe_turn = lambda *args, **kwargs: None
    sys.modules["gaslit.agents.scribe"] = scribe

    embeddings = types.ModuleType("gaslit.embeddings")

    class EmbeddingServiceError(RuntimeError):
        pass

    embeddings.EmbeddingServiceError = EmbeddingServiceError
    sys.modules["gaslit.embeddings"] = embeddings

    captured = types.SimpleNamespace(unprotected=[], gaslit=[])
    librarian = types.ModuleType("gaslit.retrieval.librarian")

    def retrieve_unprotected(message, context):
        captured.unprotected.append((message, context))
        return []

    def retrieve_with_audit(message, context):
        captured.gaslit.append((message, context))
        return {
            "memories": [],
            "filtered": [],
            "contract": {"contract_id": "test_contract"},
        }

    librarian.retrieve_unprotected = retrieve_unprotected
    librarian.retrieve_with_audit = retrieve_with_audit
    librarian.captured = captured
    sys.modules["gaslit.retrieval.librarian"] = librarian

    contracts = types.ModuleType("gaslit.retrieval.contracts")
    contracts.seed_demo_contracts = lambda *args, **kwargs: None
    sys.modules["gaslit.retrieval.contracts"] = contracts

    sys.modules.pop("api.main", None)
    return importlib.import_module("api.main")


def test_agent_retrieval_is_scoped_to_request_user() -> None:
    api_main = _install_api_import_stubs()

    req = api_main.AgentRequest(
        message="Can you process a refund?",
        user_id="tenant_a_user",
        thread_id="thread_1",
        turn_number=7,
        tool_name="refund_request",
    )

    api_main.unprotected_agent(req)
    api_main.gaslit_agent(req)

    captured = sys.modules["gaslit.retrieval.librarian"].captured
    assert captured.unprotected[0][1]["user_id"] == "tenant_a_user"
    assert captured.gaslit[0][1]["user_id"] == "tenant_a_user"


async def _capture_voice_turns() -> list[tuple[str, str, int, str]]:
    calls: list[tuple[str, str, int, str]] = []
    scribe = types.ModuleType("gaslit.agents.scribe")

    def scribe_turn(user_id, thread_id, turn_number, transcript):
        calls.append((user_id, thread_id, turn_number, transcript))
        return {"memory_id": f"m_{turn_number}"}

    scribe.scribe_turn = scribe_turn
    sys.modules["gaslit.agents.scribe"] = scribe

    hooks = importlib.import_module("gaslit.voice.backend_hooks")
    await hooks.on_voice_transcript("First persistent fact.", "attacker room", "livekit")
    await hooks.on_voice_transcript("Second persistent fact.", "attacker room", "livekit")
    await hooks.on_voice_transcript("  first   persistent FACT.  ", "attacker room", "fallback")
    return calls


def test_voice_transcripts_do_not_all_share_one_turn_number() -> None:
    calls = asyncio.run(_capture_voice_turns())

    assert calls[0][0:2] == ("voice:attacker_room", "thread:attacker_room")
    assert calls[0][2] != calls[1][2], "distinct voice utterances must not collide"
    assert calls[0][2] == calls[2][2], "duplicate transcript deliveries stay idempotent"


def main() -> int:
    test_agent_retrieval_is_scoped_to_request_user()
    test_voice_transcripts_do_not_all_share_one_turn_number()
    print("isolation regression tests PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
