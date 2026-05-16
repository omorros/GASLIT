"""Dependency-free regression tests for high-impact isolation bugs.

These tests stub external services so they can run in the Cloud runner without
FastAPI, PyMongo, Anthropic, Voyage, or Atlas credentials.
"""
from __future__ import annotations

import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _BaseModel:
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FastAPI:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def add_middleware(self, *args: Any, **kwargs: Any) -> None:
        pass

    def include_router(self, *args: Any, **kwargs: Any) -> None:
        pass

    def on_event(self, *args: Any, **kwargs: Any):
        def decorator(fn):
            return fn

        return decorator

    def get(self, *args: Any, **kwargs: Any):
        def decorator(fn):
            return fn

        return decorator

    def post(self, *args: Any, **kwargs: Any):
        def decorator(fn):
            return fn

        return decorator


class _HTTPException(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _MongoClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __getitem__(self, name: str) -> dict[str, Any]:
        return {}


def _install_api_stubs(contexts: dict[str, list[dict[str, Any]]]) -> None:
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv

    fastapi = types.ModuleType("fastapi")
    fastapi.FastAPI = _FastAPI
    fastapi.HTTPException = _HTTPException
    fastapi.Query = lambda default, *args, **kwargs: default
    sys.modules["fastapi"] = fastapi

    fastapi_middleware = types.ModuleType("fastapi.middleware")
    fastapi_cors = types.ModuleType("fastapi.middleware.cors")
    fastapi_cors.CORSMiddleware = object
    sys.modules["fastapi.middleware"] = fastapi_middleware
    sys.modules["fastapi.middleware.cors"] = fastapi_cors

    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = _BaseModel
    pydantic.Field = lambda default=None, **kwargs: (
        kwargs["default_factory"]() if "default_factory" in kwargs else default
    )
    sys.modules["pydantic"] = pydantic

    pymongo = types.ModuleType("pymongo")
    pymongo.MongoClient = _MongoClient
    sys.modules["pymongo"] = pymongo

    scribe = types.ModuleType("gaslit.agents.scribe")
    scribe.scribe_turn = lambda *args, **kwargs: None
    sys.modules["gaslit.agents.scribe"] = scribe

    embeddings = types.ModuleType("gaslit.embeddings")
    embeddings.EmbeddingServiceError = RuntimeError
    sys.modules["gaslit.embeddings"] = embeddings

    librarian = types.ModuleType("gaslit.retrieval.librarian")

    def retrieve_unprotected(query_text: str, tool_context: dict[str, Any]):
        contexts["unprotected"].append(tool_context)
        return []

    def retrieve_with_audit(query_text: str, tool_context: dict[str, Any]):
        contexts["gaslit"].append(tool_context)
        return {
            "memories": [],
            "filtered": [],
            "contract": {"contract_id": "c_test"},
        }

    librarian.retrieve_unprotected = retrieve_unprotected
    librarian.retrieve_with_audit = retrieve_with_audit
    sys.modules["gaslit.retrieval.librarian"] = librarian

    contracts = types.ModuleType("gaslit.retrieval.contracts")
    contracts.seed_demo_contracts = lambda *args, **kwargs: None
    sys.modules["gaslit.retrieval.contracts"] = contracts

    schemas = types.ModuleType("gaslit.schemas")
    schemas.MEMORIES = "memories"
    schemas.QUARANTINE = "quarantine"
    schemas.RETRIEVAL_LOG = "retrieval_log"
    schemas.DB_NAME = "gaslit"
    schemas.bootstrap_collections = lambda *args, **kwargs: None
    schemas.seed_agent_registry = lambda *args, **kwargs: None
    sys.modules["gaslit.schemas"] = schemas

    for module_name, attr in (
        ("gaslit.adversary.minja_simulator", "router"),
        ("api.compliance_export", "router"),
        ("gaslit.agents.sentinel", "sentinel_router"),
        ("gaslit.voice.router", "voice_router"),
        ("api.demo_dashboard", "router"),
    ):
        module = types.ModuleType(module_name)
        setattr(module, attr, object())
        sys.modules[module_name] = module


def _load_api_main_with_stubs():
    contexts: dict[str, list[dict[str, Any]]] = {"unprotected": [], "gaslit": []}
    _install_api_stubs(contexts)
    sys.modules.pop("api.main", None)
    return importlib.import_module("api.main"), contexts


class IsolationRegressionTests(unittest.TestCase):
    def test_agent_retrieval_is_scoped_to_request_user(self) -> None:
        api_main, contexts = _load_api_main_with_stubs()
        req = api_main.AgentRequest(
            message="Can you process a refund?",
            user_id="u_alice",
            thread_id="t_123",
            turn_number=7,
            tool_name="refund_request",
        )

        api_main.unprotected_agent(req)
        api_main.gaslit_agent(req)

        self.assertEqual(contexts["unprotected"][0]["user_id"], "u_alice")
        self.assertEqual(contexts["gaslit"][0]["user_id"], "u_alice")

    def test_voice_transcript_ids_keep_retries_idempotent_without_losing_turns(self) -> None:
        calls: list[tuple[str, str, int, str]] = []
        scribe = types.ModuleType("gaslit.agents.scribe")

        def scribe_turn(user_id: str, thread_id: str, turn_number: int, transcript: str):
            calls.append((user_id, thread_id, turn_number, transcript))
            return {"memory_id": f"m_{turn_number}"}

        scribe.scribe_turn = scribe_turn
        sys.modules["gaslit.agents.scribe"] = scribe

        from gaslit.voice import backend_hooks

        asyncio.run(backend_hooks.on_voice_transcript("First transcript", "attacker room", "livekit"))
        asyncio.run(backend_hooks.on_voice_transcript("Second transcript", "attacker room", "livekit"))
        asyncio.run(backend_hooks.on_voice_transcript("  FIRST   TRANSCRIPT  ", "attacker room", "livekit"))

        self.assertEqual(calls[0][0], "voice:attacker_room")
        self.assertEqual(calls[0][1], "thread:attacker_room")
        self.assertNotEqual(calls[0][2], calls[1][2])
        self.assertEqual(calls[0][2], calls[2][2])


if __name__ == "__main__":
    unittest.main()
