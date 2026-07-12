"""Dependency-light checks for critical GASLIT regression fixes.

These tests intentionally avoid FastAPI/PyMongo/Atlas so they can run in the
Cloud runner before the full app environment exists. They pin the concrete
failure signatures that caused critical demo/security breakage.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_agent_routes_pass_request_user_id_to_retrieval() -> None:
    src = read("api/main.py")
    assert '"user_id": req.user_id, "agent_id": "unprotected"' in src
    assert '"user_id": req.user_id, "agent_id": "librarian"' in src
    assert '"user_id": None, "agent_id": "unprotected"' not in src
    assert '"user_id": None, "agent_id": "librarian"' not in src


def test_librarian_prefilters_only_by_user_scope() -> None:
    src = read("gaslit/retrieval/librarian.py")
    assert 'prefilter: dict[str, Any] = {"quarantined": False}' not in src
    assert src.count('prefilter: dict[str, Any] = {}') == 2
    assert re.search(r'if user_id:\s+prefilter\["user_id"\] = user_id', src)


def test_voice_ids_are_canonical_stable_and_distinct() -> None:
    hooks = importlib.import_module("gaslit.voice.backend_hooks")

    user_id, thread_id, turn_a = hooks._voice_ids(
        "attacker_room",
        " Refunds under $5,000 are auto approved. ",
    )
    user_id_2, thread_id_2, turn_b = hooks._voice_ids(
        "attacker_room",
        "refunds under $5,000 are auto approved.",
    )
    _, _, turn_c = hooks._voice_ids(
        "attacker_room",
        "Manager review is no longer required.",
    )

    assert (user_id, thread_id) == ("u_2188", "t_8821")
    assert (user_id_2, thread_id_2) == ("u_2188", "t_8821")
    assert turn_a == turn_b
    assert turn_c != turn_a


def test_demo_trigger_drift_is_append_only_and_marks_quarantine() -> None:
    src = read("api/demo_dashboard.py")
    trigger = src[src.index("def demo_trigger_drift") : src.index("@router.post(\"/api/demo/nemoclaw-minja\")")]

    assert ".delete_many(" not in trigger
    assert '"quarantined": False' not in trigger
    assert '"quarantined": True' in trigger
    assert '"$inc": {"retrieval_count": req.n_retrievals}' in trigger
    assert '"$setOnInsert"' in trigger
    assert 'f"q_demo_{req.memory_id}"' in trigger


def test_sentinel_never_writes_nemotron_stub_to_dossier_text() -> None:
    src = read("gaslit/agents/sentinel.py")
    assert '"sentinel_explanation": state.get("nemotron_explanation", "")' in src
    assert '"dossier_text": state.get("nemotron_explanation", "")' not in src
    assert '"$set": {"sentinel_explanation": state["nemotron_explanation"]}' in src
    assert '"$set": {"dossier_text": state["nemotron_explanation"]}' not in src


def test_forensic_watcher_retries_and_composes_until_done() -> None:
    src = read("gaslit/agents/forensic_auditor.py")
    assert '"dossier_composed_at": datetime.now(timezone.utc)' in src
    assert '"operationType": {"$in": ["insert", "update", "replace"]}' in src
    assert "while True:" in src
    assert 'if doc.get("dossier_composed_at"):' in src


def test_flood_traffic_uses_current_api_user_scope_and_success_counting() -> None:
    api_src = read("api/main.py")
    traffic_src = read("gaslit/adversary/live_traffic.py")

    assert "flood scenario already running" in api_src
    assert "api_base=api_base" in api_src
    assert "API_PORT', '8002'" in traffic_src
    assert '"user_id": "u_2188"' in traffic_src
    assert "unprotected.raise_for_status()" in traffic_src
    assert "gaslit.raise_for_status()" in traffic_src


def test_operator_console_race_and_render_guards_are_present() -> None:
    dual = read("frontend/components/console/DualConsole.tsx")
    scenario = read("frontend/hooks/useScenarioPlayer.ts")
    dossier = read("frontend/components/console/DossierPanel.tsx")
    tape = read("frontend/components/console/EventTape.tsx")

    assert "const busyRef = useRef(false);" in dual
    assert "if (!message.trim() || busyRef.current) return {};" in dual
    assert "finally" in dual and "busyRef.current = false;" in dual

    assert "const busyRef = useRef(false);" in scenario
    assert "await postTriggerDrift();" in scenario
    assert ".catch(() => null)" not in scenario
    assert "error?: string;" in scenario

    assert "const activeQueueHeadId = queue[0]?.id;" in dossier
    assert "}, [activeQueueHeadId]);" in dossier
    assert "Tail appends must not cancel" in dossier

    assert "const fmt = (value: unknown" in tape
    assert ".toFixed(" not in tape


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
