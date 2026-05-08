from api import main as api_main


def test_unprotected_agent_passes_request_user_to_retrieval(monkeypatch):
    seen_contexts = []

    monkeypatch.setattr(api_main, "scribe_turn", lambda *args, **kwargs: None)

    def fake_retrieve(query_text, tool_context):
        seen_contexts.append(tool_context)
        return []

    monkeypatch.setattr(api_main, "retrieve_unprotected", fake_retrieve)

    response = api_main.unprotected_agent(
        api_main.AgentRequest(
            message="Can you process a refund?",
            user_id="u_alice",
            thread_id="t_1",
            turn_number=1,
            tool_name="refund_request",
        )
    )

    assert response.agent_id == "unprotected"
    assert seen_contexts == [
        {"tool_name": "refund_request", "user_id": "u_alice", "agent_id": "unprotected"}
    ]


def test_gaslit_agent_passes_request_user_to_retrieval(monkeypatch):
    seen_contexts = []

    monkeypatch.setattr(api_main, "scribe_turn", lambda *args, **kwargs: None)

    def fake_retrieve(query_text, tool_context):
        seen_contexts.append(tool_context)
        return {
            "memories": [],
            "filtered": [],
            "contract": {
                "contract_id": "refund_request:v1",
                "tier": "high_stakes",
                "rank_weights": {},
            },
        }

    monkeypatch.setattr(api_main, "retrieve_with_audit", fake_retrieve)

    response = api_main.gaslit_agent(
        api_main.AgentRequest(
            message="Can you process a refund?",
            user_id="u_bob",
            thread_id="t_1",
            turn_number=1,
            tool_name="refund_request",
        )
    )

    assert response.agent_id == "gaslit"
    assert seen_contexts == [
        {"tool_name": "refund_request", "user_id": "u_bob", "agent_id": "librarian"}
    ]
