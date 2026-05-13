"""Smoke test — agent endpoints preserve user scope for retrieval.

Pure unit test, no DB or provider credentials needed.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from api import main as api_main


def _request(user_id: str = "u_alice") -> api_main.AgentRequest:
    return api_main.AgentRequest(
        message="Can you look up my latest order?",
        user_id=user_id,
        thread_id="t_scope",
        turn_number=1,
        tool_name="lookup_order",
    )


def _without_scribe() -> Callable[..., None]:
    original_scribe = api_main.scribe_turn
    api_main.scribe_turn = lambda *args, **kwargs: None
    return original_scribe


def test_unprotected_agent_passes_request_user_id_to_retrieval() -> None:
    captured: dict[str, Any] = {}
    original_scribe = _without_scribe()
    original_retrieve = api_main.retrieve_unprotected

    def fake_retrieve(message: str, tool_context: dict[str, Any]) -> list[dict[str, Any]]:
        captured["message"] = message
        captured["tool_context"] = tool_context
        return []

    try:
        api_main.retrieve_unprotected = fake_retrieve
        response = api_main.unprotected_agent(_request("u_alice"))
    finally:
        api_main.retrieve_unprotected = original_retrieve
        api_main.scribe_turn = original_scribe

    assert response.agent_id == "unprotected"
    assert captured["tool_context"]["user_id"] == "u_alice"
    assert captured["tool_context"]["tool_name"] == "lookup_order"


def test_gaslit_agent_passes_request_user_id_to_retrieval() -> None:
    captured: dict[str, Any] = {}
    original_scribe = _without_scribe()
    original_retrieve = api_main.retrieve_with_audit

    def fake_retrieve(message: str, tool_context: dict[str, Any]) -> dict[str, Any]:
        captured["message"] = message
        captured["tool_context"] = tool_context
        return {
            "memories": [],
            "filtered": [],
            "contract": {
                "contract_id": "read_only_lookup_order",
                "tier": "read_only",
                "rank_weights": {},
            },
        }

    try:
        api_main.retrieve_with_audit = fake_retrieve
        response = api_main.gaslit_agent(_request("u_bob"))
    finally:
        api_main.retrieve_with_audit = original_retrieve
        api_main.scribe_turn = original_scribe

    assert response.agent_id == "gaslit"
    assert captured["tool_context"]["user_id"] == "u_bob"
    assert captured["tool_context"]["tool_name"] == "lookup_order"


if __name__ == "__main__":
    test_unprotected_agent_passes_request_user_id_to_retrieval()
    test_gaslit_agent_passes_request_user_id_to_retrieval()
    print("agent_user_scope smoke tests PASS")
