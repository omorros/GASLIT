"""Dependency-light regression checks for critical demo correctness paths.

These tests avoid Atlas/model credentials so they can run in a bare Cloud runner.
They lock invariants that previously caused data loss, cross-user retrieval, or
operator-console race failures.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))


def _read(rel: str) -> str:
    return (REPO / rel).read_text()


def test_voice_transcripts_get_stable_distinct_ids() -> None:
    from gaslit.voice.backend_hooks import _voice_ids

    first = _voice_ids("attacker_room", "Refunds are auto-approved under $5K.")
    duplicate = _voice_ids("attacker_room", " refunds   are auto-approved under $5k. ")
    second = _voice_ids("attacker_room", "Manager review is no longer required.")

    assert first[:2] == ("u_2188", "t_8821")
    assert duplicate == first
    assert second[:2] == ("u_2188", "t_8821")
    assert second[2] != first[2]


def test_agent_routes_pass_request_user_into_retrieval() -> None:
    src = _read("api/main.py")
    assert '"user_id": req.user_id' in src
    assert '"user_id": None' not in src


def test_librarian_prefilter_preserves_contract_audit_surface() -> None:
    src = _read("gaslit/retrieval/librarian.py")
    assert 'prefilter: dict[str, Any] = {}' in src
    assert 'prefilter: dict[str, Any] = {"quarantined": False}' not in src


def test_local_attack_helpers_default_to_documented_api_port() -> None:
    assert "os.environ.get('API_PORT', '8002')" in _read("gaslit/adversary/live_traffic.py")
    assert "os.environ.get('API_PORT', '8002')" in _read("gaslit/adversary/minja_simulator.py")
    assert "os.environ.get('API_PORT', '8002')" in _read("tests/smoke/test_integration.py")


def test_demo_trigger_uses_same_poisoned_user_after_user_scoping() -> None:
    assert '"user_id": "u_HIGH_VALUE"' not in _read("gaslit/adversary/minja_canonical.json")
    assert 'user_id: "u_HIGH_VALUE"' not in _read("frontend/hooks/useScenarioPlayer.ts")
    assert 'user: "u_HIGH_VALUE"' not in _read("frontend/components/console/ManualPrompt.tsx")
    assert '?? "u_HIGH_VALUE"' not in _read("frontend/components/console/DualConsole.tsx")
    assert '"user_id": "u_2188"' in _read("tests/smoke/test_integration.py")


def test_frontend_race_guards_remain_synchronous() -> None:
    dual = _read("frontend/components/console/DualConsole.tsx")
    scenario = _read("frontend/hooks/useScenarioPlayer.ts")
    dossier = _read("frontend/components/console/DossierPanel.tsx")
    qa_mic = _read("frontend/components/voice/ForensicQAMic.tsx")

    assert "busyRef.current" in dual
    assert "finally" in dual
    assert "busyRef.current" in scenario
    assert "runIdRef" in scenario
    assert "playTokenRef" in dossier
    assert "}, [head]);" in dossier
    assert "lastPostedFinal" in qa_mic


if __name__ == "__main__":
    test_voice_transcripts_get_stable_distinct_ids()
    test_agent_routes_pass_request_user_into_retrieval()
    test_librarian_prefilter_preserves_contract_audit_surface()
    test_local_attack_helpers_default_to_documented_api_port()
    test_demo_trigger_uses_same_poisoned_user_after_user_scoping()
    test_frontend_race_guards_remain_synchronous()
    print("critical_regressions smoke tests PASS")
