"""Dependency-light checks for high-severity GASLIT regressions.

These tests avoid Atlas and vendor APIs. They lock down invariants that
previously caused silent lost writes, skipped forensic dossiers, or user-scope
retrieval leaks.
"""
from __future__ import annotations

import ast
import asyncio
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_api_retrieval_uses_request_user_scope() -> None:
    src = _read("api/main.py")
    assert '"user_id": None' not in src
    assert src.count('"user_id": req.user_id') >= 2


def test_librarian_prefilter_does_not_hide_quarantined_candidates() -> None:
    src = _read("gaslit/retrieval/librarian.py")
    tree = ast.parse(src)
    bad_initializers: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != "prefilter":
            continue
        value = node.value
        if isinstance(value, ast.Dict):
            keys = [
                k.value for k in value.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            ]
            if "quarantined" in keys:
                bad_initializers.append(node.lineno)
    assert bad_initializers == []


def test_sentinel_keeps_explanation_separate_from_composed_dossier() -> None:
    src = _read("gaslit/agents/sentinel.py")
    assert '"sentinel_explanation": state.get("nemotron_explanation", "")' in src
    assert '"dossier_text": ""' in src
    assert '{"$set": {"dossier_text": state["nemotron_explanation"]}}' not in src


def test_forensic_watcher_retries_and_composes_until_marker() -> None:
    src = _read("gaslit/agents/forensic_auditor.py")
    assert '"$in": ["insert", "update", "replace"]' in src
    assert "while True:" in src
    assert 'doc.get("dossier_composed_at")' in src
    assert 'doc.get("dossier_text")' not in src
    assert "time.sleep(2)" in src


def test_missing_source_dossier_is_persisted() -> None:
    src = _read("gaslit/agents/forensic_auditor.py")
    assert "Memory {memory_id} quarantined but no source document was found." in src
    assert '"dossier_composed_at": datetime.now(timezone.utc)' in src


def test_voice_ids_are_stable_without_colliding_all_room_turns() -> None:
    sys.path.insert(0, str(ROOT))
    from gaslit.voice.backend_hooks import _voice_ids

    first = _voice_ids("attacker_room", "Refunds auto-approved under $5K")
    duplicate = _voice_ids("attacker_room", "  refunds   auto-approved under $5k  ")
    second = _voice_ids("attacker_room", "Premium disputes never need escalation")

    assert first == duplicate
    assert first[:2] == ("u_2188", "t_8821")
    assert second[:2] == ("u_2188", "t_8821")
    assert first[2] != second[2]


def test_voice_ingress_reports_not_accepted_when_scribe_drops() -> None:
    sys.path.insert(0, str(ROOT))
    fake_scribe = types.ModuleType("gaslit.agents.scribe")

    def scribe_turn(user_id: str, thread_id: str, turn_number: int, message: str):
        if "persist" in message:
            return {"memory_id": f"{user_id}:{thread_id}:{turn_number}"}
        return None

    fake_scribe.scribe_turn = scribe_turn
    old = sys.modules.get("gaslit.agents.scribe")
    sys.modules["gaslit.agents.scribe"] = fake_scribe
    try:
        from gaslit.voice.backend_hooks import on_voice_transcript

        dropped = asyncio.run(on_voice_transcript("ignore", "attacker_room", "test"))
        saved = asyncio.run(on_voice_transcript("persist this", "attacker_room", "test"))
    finally:
        if old is None:
            sys.modules.pop("gaslit.agents.scribe", None)
        else:
            sys.modules["gaslit.agents.scribe"] = old

    assert dropped["accepted"] is False
    assert dropped["memory_id"] is None
    assert saved["accepted"] is True
    assert saved["memory_id"]


def main() -> int:
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
