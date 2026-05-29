"""Dependency-light regression checks for critical API correctness paths."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")


def test_agent_routes_pass_request_user_to_retrieval() -> None:
    import api.main as main

    captured: dict[str, dict] = {}
    original_scribe = main.scribe_turn
    original_unprotected = main.retrieve_unprotected
    original_protected = main.retrieve_with_audit

    def fake_scribe(*_args, **_kwargs):
        return None

    def fake_unprotected(_query_text: str, tool_context: dict) -> list[dict]:
        captured["unprotected"] = dict(tool_context)
        return []

    def fake_protected(_query_text: str, tool_context: dict) -> dict:
        captured["protected"] = dict(tool_context)
        return {
            "memories": [],
            "filtered": [],
            "contract": {"contract_id": "high_stakes_refund_request"},
        }

    try:
        main.scribe_turn = fake_scribe
        main.retrieve_unprotected = fake_unprotected
        main.retrieve_with_audit = fake_protected

        request = main.AgentRequest(
            message="Can you process a $4,800 refund?",
            user_id="u_customer_a",
            thread_id="t_regression",
            turn_number=1,
            tool_name="refund_request",
        )
        main.unprotected_agent(request)
        main.gaslit_agent(request)
    finally:
        main.scribe_turn = original_scribe
        main.retrieve_unprotected = original_unprotected
        main.retrieve_with_audit = original_protected

    assert captured["unprotected"]["user_id"] == "u_customer_a"
    assert captured["protected"]["user_id"] == "u_customer_a"


def test_scenario_flood_rejects_remote_without_token() -> None:
    import api.main as main
    from fastapi import HTTPException

    old_token = os.environ.pop("SCENARIO_FLOOD_TOKEN", None)
    try:
        remote_request = SimpleNamespace(
            client=SimpleNamespace(host="203.0.113.10"),
            headers={},
        )
        try:
            main._authorize_flood_request(remote_request)
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError("remote flood request without token was accepted")

        loopback_request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            headers={},
        )
        main._authorize_flood_request(loopback_request)

        os.environ["SCENARIO_FLOOD_TOKEN"] = "demo-secret"
        token_request = SimpleNamespace(
            client=SimpleNamespace(host="203.0.113.10"),
            headers={"x-gaslit-demo-token": "demo-secret"},
        )
        main._authorize_flood_request(token_request)
    finally:
        if old_token is None:
            os.environ.pop("SCENARIO_FLOOD_TOKEN", None)
        else:
            os.environ["SCENARIO_FLOOD_TOKEN"] = old_token


if __name__ == "__main__":
    test_agent_routes_pass_request_user_to_retrieval()
    test_scenario_flood_rejects_remote_without_token()
    print("api_regressions smoke tests PASS")
