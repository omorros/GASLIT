"""Normalize LiveKit / client-originated transcript payloads before Scribe."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VoiceInputPayload(BaseModel):
    """POST /api/voice-input body."""

    transcript: str = Field(..., min_length=1, max_length=32_000)
    source: str | None = Field(default="livekit", description="livekit | fallback | web-speech")
    room: str | None = Field(default=None, description="attacker_room | forensic_room")
    user_id: str | None = Field(default=None, description="Optional explicit Scribe user_id")
    thread_id: str | None = Field(default=None, description="Optional explicit Scribe thread_id")
    turn_number: int | None = Field(default=None, ge=1, description="Optional explicit Scribe turn")


def normalize_transcript(raw: str) -> str:
    return " ".join(raw.strip().split())


def to_scribe_event(payload: VoiceInputPayload) -> dict:
    """Normalize payload for `on_voice_transcript` → `scribe_turn`."""
    return {
        "transcript": normalize_transcript(payload.transcript),
        "source": payload.source or "livekit",
        "room": payload.room,
        "user_id": payload.user_id,
        "thread_id": payload.thread_id,
        "turn_number": payload.turn_number,
    }
