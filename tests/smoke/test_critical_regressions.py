"""Smoke coverage for high-severity regressions found by critical-bug audits.

These tests intentionally avoid network and database dependencies so they can
run in the Cloud runner while still locking the concrete data-loss/race fixes.
"""

from pathlib import Path

from gaslit.voice import backend_hooks


ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text()


def test_voice_transcripts_use_stable_distinct_turn_ids() -> None:
    first = backend_hooks._voice_ids("attacker_room", "Refunds are auto approved.")
    duplicate = backend_hooks._voice_ids("attacker_room", "  refunds   are AUTO approved. ")
    second = backend_hooks._voice_ids("attacker_room", "Please approve the refund now.")

    assert first[:2] == ("u_2188", "t_8821")
    assert duplicate == first
    assert second[:2] == first[:2]
    assert second[2] != first[2]


def test_agent_retrieval_is_user_scoped_and_contract_filtered() -> None:
    api_main = read("api/main.py")
    librarian = read("gaslit/retrieval/librarian.py")

    assert '{"tool_name": tool_name, "user_id": req.user_id, "agent_id": "unprotected"}' in api_main
    assert '{"tool_name": tool_name, "user_id": req.user_id, "agent_id": "librarian"}' in api_main
    assert '"user_id": None' not in api_main
    assert 'prefilter: dict[str, Any] = {"quarantined": False}' not in librarian
    assert 'prefilter["user_id"] = user_id' in librarian


def test_quarantine_dossiers_are_enriched_without_overwrite_or_delete() -> None:
    sentinel = read("gaslit/agents/sentinel.py")
    forensic = read("gaslit/agents/forensic_auditor.py")
    demo = read("api/demo_dashboard.py")

    assert '"sentinel_explanation": state.get("nemotron_explanation", "")' in sentinel
    assert '"dossier_text": ""' in sentinel
    assert '"$set": {"sentinel_explanation": state["nemotron_explanation"]}' in sentinel
    assert '"$set": {"dossier_text": state["nemotron_explanation"]}' not in sentinel

    assert 'if doc.get("dossier_composed_at"):' in forensic
    assert '"operationType": {"$in": ["insert", "update", "replace"]}' in forensic
    assert "while True:" in forensic
    assert "time.sleep(2)" in forensic

    trigger_drift = demo[demo.index("def demo_trigger_drift") :]
    assert ".delete_many" not in trigger_drift
    assert '"quarantined": True' in trigger_drift
    assert '"$setOnInsert"' in trigger_drift
    assert "upsert=True" in trigger_drift


def test_frontend_inflight_and_audio_guards_are_present() -> None:
    dual = read("frontend/components/console/DualConsole.tsx")
    dossier = read("frontend/components/console/DossierPanel.tsx")
    scenario = read("frontend/hooks/useScenarioPlayer.ts")
    header = read("frontend/components/console/ScenarioHeader.tsx")
    qa_mic = read("frontend/components/voice/ForensicQAMic.tsx")

    assert "const busyRef = useRef(false)" in dual
    assert "busyRef.current = true" in dual
    assert "busyRef.current = false" in dual

    assert "const queueHeadId = queue[0]?.id ?? null" in dossier
    assert "}, [queueHeadId]);" in dossier
    assert "playingRef.current = false" in dossier

    assert "const advancingRef = useRef(false)" in scenario
    assert "state.busy || advancingRef.current" in scenario
    assert "await postTriggerDrift();" in scenario
    assert ".catch(() => null)" not in scenario
    assert "Scenario backend error:" in header

    assert "const lastPostedFinal = useRef<string | null>(null)" in qa_mic
    assert "const qaBusyRef = useRef(false)" in qa_mic
    assert "finalText === lastPostedFinal.current || qaBusyRef.current" in qa_mic
