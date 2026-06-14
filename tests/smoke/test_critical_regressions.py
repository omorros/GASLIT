"""Dependency-light checks for critical demo and data-safety regressions.

These assertions deliberately inspect source for invariants that otherwise need
Atlas, provider credentials, or a browser to reproduce.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def read(rel: str) -> str:
    return (ROOT / rel).read_text()


def body(source: str, name: str) -> str:
    match = re.search(rf"^def {name}\(.*?^def ", source, flags=re.M | re.S)
    if match:
        return match.group(0).rsplit("\ndef ", 1)[0]
    match = re.search(rf"^def {name}\(.*", source, flags=re.M | re.S)
    assert match, f"{name} not found"
    return match.group(0)


def test_demo_trigger_drift_is_append_only() -> None:
    drift = body(read("api/demo_dashboard.py"), "demo_trigger_drift")
    assert ".delete_many(" not in drift
    assert '"$setOnInsert"' in drift
    assert "upsert=True" in drift
    assert '"quarantined": True' in drift


def test_agent_retrieval_is_user_scoped() -> None:
    api = read("api/main.py")
    assert '"user_id": None' not in api
    assert '"user_id": req.user_id' in api


def test_contract_filtering_sees_quarantined_candidates() -> None:
    librarian = read("gaslit/retrieval/librarian.py")
    assert 'prefilter: dict[str, Any] = {"quarantined": False}' not in librarian
    assert "filtered_out.append" in librarian


def test_sentinel_does_not_preempt_forensic_dossier() -> None:
    sentinel = read("gaslit/agents/sentinel.py")
    assert '"sentinel_explanation": state.get("nemotron_explanation", "")' in sentinel
    assert '"dossier_text": state.get("nemotron_explanation", "")' not in sentinel
    assert '"$set": {"sentinel_explanation": state["nemotron_explanation"]}' in sentinel


def test_forensic_watcher_retries_until_dossier_composed() -> None:
    auditor = read("gaslit/agents/forensic_auditor.py")
    assert '"operationType": {"$in": ["insert", "update", "replace"]}' in auditor
    assert 'doc.get("dossier_composed_at")' in auditor
    assert "time.sleep(2.0)" in auditor


def test_voice_transcript_ids_are_idempotent_without_colliding() -> None:
    from gaslit.voice.backend_hooks import _voice_ids

    first = _voice_ids("attacker_room", "Refunds under five thousand are automatic.")
    duplicate = _voice_ids("attacker_room", "  refunds UNDER five thousand are automatic. ")
    second = _voice_ids("attacker_room", "Manager review is no longer required.")

    assert first == duplicate
    assert first[:2] == ("u_2188", "t_8821")
    assert second[:2] == ("u_2188", "t_8821")
    assert first[2] != second[2]


def test_console_dispatch_and_reset_guards_are_wired() -> None:
    dual = read("frontend/components/console/DualConsole.tsx")
    page = read("frontend/app/console/page.tsx")
    scenario = read("frontend/hooks/useScenarioPlayer.ts")

    assert "busyRef.current" in dual
    assert "setDispatchBusy(true)" in dual
    assert "finally" in dual and "setDispatchBusy(false)" in dual
    assert "busyRef.current" in scenario
    assert "advanceScenario" in page
    assert "scenario.state.busy || scribeBusy" in page
    assert "resetSimulation" in page
    assert "dualHandleRef.current?.reset()" in page
    assert "ev.reset()" in page
    assert "key={resetEpoch}" in page


def test_adversary_traffic_defaults_to_project_api_port() -> None:
    assert "os.environ.get('API_PORT', '8002')" in read("gaslit/adversary/live_traffic.py")
    assert "os.environ.get('API_PORT', '8002')" in read("gaslit/adversary/minja_simulator.py")


def main() -> int:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("critical_regressions smoke test PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
