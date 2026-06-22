"""Dependency-light regression checks for critical demo correctness bugs.

These checks intentionally avoid Atlas/API/browser startup. They guard the
source-level invariants behind the high-impact bugs fixed in this branch:
user-scoped retrieval, non-destructive drift injection, forensic dossier
composition, voice transcript ID stability, and console race guards.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def read(rel: str) -> str:
    return (ROOT / rel).read_text()


def function_body(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.index(marker)
    next_def = source.find("\ndef ", start + len(marker))
    next_async_def = source.find("\nasync def ", start + len(marker))
    stops = [i for i in (next_def, next_async_def) if i != -1]
    end = min(stops) if stops else len(source)
    return source[start:end]


def test_retrieval_is_user_scoped_and_contract_filters_quarantine() -> None:
    api = read("api/main.py")
    assert '"user_id": None' not in api, "agent routes must not drop req.user_id before retrieval"
    assert '"user_id": req.user_id' in api

    librarian = read("gaslit/retrieval/librarian.py")
    assert librarian.count("prefilter: dict[str, Any] = {}") >= 2
    assert 'prefilter: dict[str, Any] = {"quarantined": False}' not in librarian


def test_voice_ids_are_stable_without_turn_collisions() -> None:
    from gaslit.voice.backend_hooks import _voice_ids

    first = _voice_ids("attacker_room", "Refund policy was changed.")
    duplicate = _voice_ids("attacker_room", "  refund   policy was CHANGED. ")
    second = _voice_ids("attacker_room", "Manager review is no longer required.")

    assert first[:2] == ("u_2188", "t_8821")
    assert first == duplicate, "duplicate STT deliveries should be idempotent"
    assert first[2] != second[2], "distinct voice turns must not overwrite turn 1"


def test_drift_injection_is_append_only_and_idempotent() -> None:
    body = function_body(read("api/demo_dashboard.py"), "demo_trigger_drift")

    assert "delete_many" not in body
    assert '"quarantined": False' not in body
    assert '"$inc": {"retrieval_count": inserted}' in body
    assert '"$setOnInsert"' in body
    assert 'f"q_{req.memory_id}_demo_trigger"' in body


def test_forensic_dossiers_are_not_overwritten_or_skipped() -> None:
    sentinel = function_body(read("gaslit/agents/sentinel.py"), "_quarantine_node")
    assert "sentinel_explanation" in sentinel
    assert '"dossier_text": state.get("nemotron_explanation"' not in sentinel
    assert '"$set": {"dossier_text": state["nemotron_explanation"]}' not in sentinel

    forensic = read("gaslit/agents/forensic_auditor.py")
    watcher = function_body(forensic, "watch_quarantine_stream")
    assert "dossier_composed_at" in watcher
    assert '"insert", "update", "replace"' in watcher
    assert "while True:" in watcher

    compose = function_body(forensic, "compose_dossier")
    assert "Memory {memory_id} quarantined but no source document was found." in compose
    assert "dossier_composed_at" in compose


def test_console_race_guards_are_synchronous() -> None:
    dossier_panel = read("frontend/components/console/DossierPanel.tsx")
    assert "activeQueueId" in dossier_panel
    assert "}, [activeQueueId]);" in dossier_panel
    assert "}, [queue]);" not in dossier_panel

    dual_console = read("frontend/components/console/DualConsole.tsx")
    assert "inFlightRef" in dual_console
    assert "if (!message.trim() || inFlightRef.current) return {};" in dual_console
    assert "inFlightRef.current = false;" in dual_console

    scenario = read("frontend/hooks/useScenarioPlayer.ts")
    assert "busyRef" in scenario
    assert "catch(() => null)" not in scenario
    assert 'user_id: "u_2188"' in scenario


def main() -> int:
    tests = [
        test_retrieval_is_user_scoped_and_contract_filters_quarantine,
        test_voice_ids_are_stable_without_turn_collisions,
        test_drift_injection_is_append_only_and_idempotent,
        test_forensic_dossiers_are_not_overwritten_or_skipped,
        test_console_race_guards_are_synchronous,
    ]
    for test in tests:
        test()
    print("critical regression smoke tests PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
