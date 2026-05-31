"""Dependency-light regression checks for critical API safety bugs.

Run from the repo root:
  python3 tests/smoke/test_api_regressions.py
"""
from __future__ import annotations

import sys
import threading
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def _install_api_dependency_stubs() -> type[Exception]:
    """Let this smoke test import api.main without installing the web stack."""

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str | None = None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class FastAPI:
        def __init__(self, *args, **kwargs):
            pass

        def add_middleware(self, *args, **kwargs) -> None:
            pass

        def include_router(self, *args, **kwargs) -> None:
            pass

        def on_event(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    class CORSMiddleware:
        pass

    class FieldInfo:
        def __init__(self, default=None):
            self.default = default

    def Field(default=None, **_kwargs):
        return FieldInfo(default)

    class BaseModel:
        def __init__(self, **kwargs):
            for cls in reversed(type(self).mro()):
                for name in getattr(cls, "__annotations__", {}):
                    default = getattr(type(self), name, None)
                    if isinstance(default, FieldInfo):
                        default = default.default
                    if name in kwargs:
                        setattr(self, name, kwargs.pop(name))
                    elif default is not None:
                        setattr(self, name, default)
            for name, value in kwargs.items():
                setattr(self, name, value)

    def Query(default=None, **_kwargs):
        return default

    class MongoClient:
        def __init__(self, *args, **kwargs):
            pass

        def __getitem__(self, _name):
            return {}

    fastapi = types.ModuleType("fastapi")
    fastapi.FastAPI = FastAPI
    fastapi.HTTPException = HTTPException
    fastapi.Query = Query
    fastapi_middleware = types.ModuleType("fastapi.middleware")
    fastapi_cors = types.ModuleType("fastapi.middleware.cors")
    fastapi_cors.CORSMiddleware = CORSMiddleware

    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = BaseModel
    pydantic.Field = Field

    pymongo = types.ModuleType("pymongo")
    pymongo.MongoClient = MongoClient
    pymongo_database = types.ModuleType("pymongo.database")
    pymongo_database.Database = object

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None

    sys.modules.setdefault("fastapi", fastapi)
    sys.modules.setdefault("fastapi.middleware", fastapi_middleware)
    sys.modules.setdefault("fastapi.middleware.cors", fastapi_cors)
    sys.modules.setdefault("pydantic", pydantic)
    sys.modules.setdefault("pymongo", pymongo)
    sys.modules.setdefault("pymongo.database", pymongo_database)
    sys.modules.setdefault("dotenv", dotenv)
    return HTTPException


HTTPException = _install_api_dependency_stubs()

import api.main as api_main


def test_agent_routes_scope_retrieval_to_request_user() -> None:
    original_scribe = api_main.scribe_turn
    original_unprotected = api_main.retrieve_unprotected
    original_audit = api_main.retrieve_with_audit
    seen: dict[str, dict] = {}

    try:
        api_main.scribe_turn = lambda *args, **kwargs: None

        def fake_unprotected(_message: str, tool_context: dict) -> list[dict]:
            seen["unprotected"] = dict(tool_context)
            return []

        def fake_audit(_message: str, tool_context: dict) -> dict:
            seen["gaslit"] = dict(tool_context)
            return {"memories": [], "filtered": [], "contract": {"contract_id": "test_contract"}}

        api_main.retrieve_unprotected = fake_unprotected
        api_main.retrieve_with_audit = fake_audit

        req = api_main.AgentRequest(
            message="Can you process a refund?",
            user_id="u_alice",
            thread_id="t_1",
            turn_number=1,
            tool_name="refund_request",
        )
        api_main.unprotected_agent(req)
        api_main.gaslit_agent(req)

        assert seen["unprotected"]["user_id"] == "u_alice"
        assert seen["gaslit"]["user_id"] == "u_alice"
    finally:
        api_main.scribe_turn = original_scribe
        api_main.retrieve_unprotected = original_unprotected
        api_main.retrieve_with_audit = original_audit


def test_scenario_flood_is_bounded_and_live_opt_in() -> None:
    original_live_module = sys.modules.get("gaslit.adversary.live_traffic")
    original_allow_live = api_main._FLOOD_ALLOW_LIVE
    entered = threading.Event()
    unblock = threading.Event()

    def fake_stream_traffic(_duration_s: int, _qps: float, *, source: str = "canned") -> int:
        assert source == "canned"
        entered.set()
        unblock.wait(timeout=2.0)
        return 7

    fake_module = types.ModuleType("gaslit.adversary.live_traffic")
    fake_module.stream_traffic = fake_stream_traffic

    try:
        with api_main._FLOOD_LOCK:
            api_main._FLOOD_RUNS.clear()
        api_main._FLOOD_ALLOW_LIVE = False
        sys.modules["gaslit.adversary.live_traffic"] = fake_module

        try:
            api_main.scenario_flood(
                api_main.FloodRequest(duration_s=2, qps=0.2, source="live"),
            )
            raise AssertionError("live flood unexpectedly started without opt-in")
        except HTTPException as exc:
            assert exc.status_code == 403

        first = api_main.scenario_flood(
            api_main.FloodRequest(duration_s=2, qps=0.2, source="canned"),
        )
        assert first.run_id.startswith("flood_")
        assert entered.wait(timeout=1.0), "flood worker did not start"

        try:
            api_main.scenario_flood(
                api_main.FloodRequest(duration_s=2, qps=0.2, source="canned"),
            )
            raise AssertionError("second active flood unexpectedly started")
        except HTTPException as exc:
            assert exc.status_code == 429

        unblock.set()
        for _ in range(40):
            status = api_main.scenario_flood_status(first.run_id)
            if status.get("status") == "completed":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("flood worker did not complete")

        status = api_main.scenario_flood_status(first.run_id)
        assert status["sent"] == 7
    finally:
        unblock.set()
        api_main._FLOOD_ALLOW_LIVE = original_allow_live
        with api_main._FLOOD_LOCK:
            api_main._FLOOD_RUNS.clear()
        if original_live_module is None:
            sys.modules.pop("gaslit.adversary.live_traffic", None)
        else:
            sys.modules["gaslit.adversary.live_traffic"] = original_live_module


if __name__ == "__main__":
    test_agent_routes_scope_retrieval_to_request_user()
    test_scenario_flood_is_bounded_and_live_opt_in()
    print("api_regressions smoke tests PASS")
