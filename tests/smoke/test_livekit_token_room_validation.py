"""Smoke test — LiveKit token requests are scoped to the two demo rooms."""

import sys
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from gaslit.voice.router import LiveKitTokenRequest


def test_livekit_token_accepts_documented_rooms():
    for room in ("attacker_room", "forensic_room"):
        req = LiveKitTokenRequest(room=room, identity="smoke-test")
        assert req.room == room


def test_livekit_token_rejects_arbitrary_rooms():
    try:
        LiveKitTokenRequest(room="private_ops_room", identity="smoke-test")
    except ValidationError:
        return
    raise AssertionError("arbitrary LiveKit room should fail validation")


if __name__ == "__main__":
    test_livekit_token_accepts_documented_rooms()
    test_livekit_token_rejects_arbitrary_rooms()
    print("livekit_token_room_validation smoke tests PASS")
