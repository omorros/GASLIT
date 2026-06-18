"""Integration hooks: voice path → Scribe + Forensic Auditor."""

from __future__ import annotations

import hashlib
import re


_CANONICAL_ROOMS: dict[str, tuple[str, str]] = {
    "attacker_room": ("u_2188", "t_8821"),
}


def _normalize_transcript(transcript: str | None) -> str:
    return re.sub(r"\s+", " ", (transcript or "").strip().lower())


def _turn_number_for_transcript(transcript: str | None) -> int:
    """Stable per-transcript turn for idempotent STT retries without collisions."""
    normalized = _normalize_transcript(transcript)
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    return int(digest[:8], 16) + 1


def _voice_ids(room: str | None, transcript: str | None = None) -> tuple[str, str, int]:
    r = (room or "voice").replace(" ", "_")
    user_id, thread_id = _CANONICAL_ROOMS.get(r, (f"voice:{r}", f"thread:{r}"))
    return user_id, thread_id, _turn_number_for_transcript(transcript)


async def on_voice_transcript(transcript: str, room: str | None, source: str | None) -> dict:
    """Forward speech-as-text into the Scribe memory pipeline."""
    from gaslit.agents.scribe import scribe_turn

    user_id, thread_id, turn_number = _voice_ids(room, transcript)
    mem = scribe_turn(user_id, thread_id, turn_number, transcript)
    return {
        "ok": True,
        "accepted": True,
        "transcript": transcript,
        "room": room,
        "source": source,
        "memory_id": (mem or {}).get("memory_id"),
    }


async def on_forensic_question(question: str, quarantine_id: str | None) -> str:
    """Dossier-grounded answer for Conv AI / UI (requires a quarantine_id)."""
    if not quarantine_id:
        return (
            "No quarantine_id provided. Open a quarantine in the UI or pass quarantine_id."
        )
    from gaslit.agents.forensic_auditor import answer_qa

    return answer_qa(question, quarantine_id)
