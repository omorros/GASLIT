"""Dependency-light regression checks for critical demo correctness paths.

These tests intentionally inspect the narrow invariants that have caused
high-impact regressions: cross-user retrieval, destructive drift injection,
voice transcript ID collisions, forensic dossier ownership, and console races.
They do not require live Atlas, Voyage, Anthropic, or a running Next.js server.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text()


def load_voice_hooks():
    path = ROOT / "gaslit" / "voice" / "backend_hooks.py"
    spec = importlib.util.spec_from_file_location("backend_hooks_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_api_retrieval_is_scoped_to_request_user() -> None:
    src = read("api/main.py")
    assert '{"tool_name": tool_name, "user_id": req.user_id, "agent_id": "unprotected"}' in src
    assert '{"tool_name": tool_name, "user_id": req.user_id, "agent_id": "librarian"}' in src
    assert '"user_id": None' not in src


def test_retrieval_keeps_quarantined_candidates_for_contract_audit() -> None:
    src = read("gaslit/retrieval/librarian.py")
    assert 'prefilter: dict[str, Any] = {}' in src
    assert 'prefilter: dict[str, Any] = {"quarantined": False}' not in src
    assert '_passes_filters(mem, contract["filters"])' in src


def test_drift_trigger_is_append_only_and_creates_demo_quarantine() -> None:
    src = read("api/demo_dashboard.py")
    drift_fn = src[src.index("def demo_trigger_drift") : src.index("@router.post(\"/api/demo/nemoclaw-minja\")")]
    assert "delete_many" not in drift_fn
    assert '"quarantined": False' not in drift_fn
    assert '"quarantined": True' in drift_fn
    assert 'upsert=True' in drift_fn
    assert 'f"q_demo_{req.memory_id}"' in drift_fn


def test_sentinel_does_not_preempt_forensic_dossier_field() -> None:
    src = read("gaslit/agents/sentinel.py")
    assert '"sentinel_explanation": state.get("nemotron_explanation", "")' in src
    assert '"dossier_text": state.get("nemotron_explanation", "")' not in src
    assert '{"$set": {"dossier_text": state["nemotron_explanation"]}}' not in src


def test_forensic_watcher_composes_until_dossier_composed_at_and_restarts() -> None:
    src = read("gaslit/agents/forensic_auditor.py")
    assert '"operationType": {"$in": ["insert", "update", "replace"]}' in src
    assert 'doc.get("dossier_composed_at")' in src
    assert 'if doc.get("dossier_text")' not in src
    assert "restarting in 2s" in src


def test_voice_ids_are_stable_for_duplicates_but_distinct_for_new_utterances() -> None:
    hooks = load_voice_hooks()
    user_a, thread_a, turn_a = hooks._voice_ids("attacker_room", "Refunds are auto approved.")
    user_dup, thread_dup, turn_dup = hooks._voice_ids(
        "attacker_room",
        "  refunds   are auto approved. ",
    )
    user_b, thread_b, turn_b = hooks._voice_ids("attacker_room", "Manager review is gone.")

    assert (user_a, thread_a) == ("u_2188", "t_8821")
    assert (user_dup, thread_dup, turn_dup) == (user_a, thread_a, turn_a)
    assert (user_b, thread_b) == (user_a, thread_a)
    assert turn_b != turn_a


def test_loopback_attack_helpers_default_to_fastapi_port_8002() -> None:
    assert "os.environ.get('API_PORT', '8002')" in read("gaslit/adversary/live_traffic.py")
    assert "os.environ.get('API_PORT', '8002')" in read("gaslit/adversary/minja_simulator.py")
    assert "raise_for_status()" in read("gaslit/adversary/live_traffic.py")
    assert "raise_for_status()" in read("gaslit/adversary/minja_simulator.py")


def test_console_sources_have_synchronous_race_guards_and_full_reset() -> None:
    dual = read("frontend/components/console/DualConsole.tsx")
    scenario = read("frontend/hooks/useScenarioPlayer.ts")
    page = read("frontend/app/console/page.tsx")
    dossier = read("frontend/components/console/DossierPanel.tsx")
    event_tape = read("frontend/components/console/EventTape.tsx")

    assert "busyRef.current" in dual
    assert "turnCounter = useRef(1000)" in dual
    assert "stateRef.current" in scenario
    assert "await postTriggerDrift();" in scenario
    assert "dualHandleRef.current?.reset();" in page
    assert "ev.reset();" in page
    assert "key={dossierKey}" in page
    assert "}, [head?.id]);" in dossier
    assert "fmtNumber(" in event_tape


if __name__ == "__main__":
    tests = [
        obj
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for test in tests:
        test()
    print(f"PASS {len(tests)} critical regression checks")
