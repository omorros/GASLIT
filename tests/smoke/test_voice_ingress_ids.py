"""Dependency-light regressions for voice transcript memory IDs.

Run with:
  python3 tests/smoke/test_voice_ingress_ids.py
"""
from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def test_voice_turn_numbers_are_stable_but_not_constant() -> None:
    from gaslit.voice.backend_hooks import _voice_ids, _voice_turn_number

    assert _voice_ids("attacker_room")[:2] == ("u_2188", "t_8821")

    first = _voice_turn_number("attacker_room", "refunds   auto-approved under $5K")
    duplicate = _voice_turn_number("attacker_room", "refunds auto-approved under $5K")
    second = _voice_turn_number("attacker_room", "manager review is no longer required")

    assert first == duplicate
    assert first != second
    assert first != 1
    assert second != 1


def test_voice_transcript_sends_distinct_turns_to_scribe() -> None:
    import gaslit.voice.backend_hooks as backend_hooks

    calls: list[tuple[str, str, int, str]] = []
    fake_scribe = types.ModuleType("gaslit.agents.scribe")

    def scribe_turn(user_id: str, thread_id: str, turn_number: int, transcript: str) -> dict:
        calls.append((user_id, thread_id, turn_number, transcript))
        return {"memory_id": f"m_{turn_number}"}

    fake_scribe.scribe_turn = scribe_turn
    old_module = sys.modules.get("gaslit.agents.scribe")
    sys.modules["gaslit.agents.scribe"] = fake_scribe
    try:
        asyncio.run(
            backend_hooks.on_voice_transcript(
                "refunds auto-approved under $5K",
                room="attacker_room",
                source="livekit",
            )
        )
        asyncio.run(
            backend_hooks.on_voice_transcript(
                "manager review is no longer required",
                room="attacker_room",
                source="livekit",
            )
        )
    finally:
        if old_module is None:
            sys.modules.pop("gaslit.agents.scribe", None)
        else:
            sys.modules["gaslit.agents.scribe"] = old_module

    assert calls[0][:2] == ("u_2188", "t_8821")
    assert calls[1][:2] == ("u_2188", "t_8821")
    assert calls[0][2] != calls[1][2]


def main() -> int:
    test_voice_turn_numbers_are_stable_but_not_constant()
    test_voice_transcript_sends_distinct_turns_to_scribe()
    print("voice ingress ID regression tests PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
