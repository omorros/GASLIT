"""Integration hooks: voice path → Scribe + Forensic Auditor."""

from __future__ import annotations

import hashlib
import re


_ROOM_IDS = {
    "attacker_room": ("u_2188", "t_8821"),
}


def _normalise_transcript(transcript: str | None) -> str:
    return re.sub(r"\s+", " ", (transcript or "").strip().lower())


def _voice_ids(room: str | None, transcript: str | None = None) -> tuple[str, str, int]:
    r = (room or "voice").replace(" ", "_")
    user_id, thread_id = _ROOM_IDS.get(r, (f"voice:{r}", f"thread:{r}"))
    normalised = _normalise_transcript(transcript)
    digest = hashlib.sha256(f"{r}|{normalised}".encode()).hexdigest()
    turn_number = int(digest[:8], 16) % 2_147_483_647 or 1
    return user_id, thread_id, turn_number


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
        "turn_number": turn_number,
    }


async def on_forensic_question(question: str, quarantine_id: str | None) -> str:
    """Dossier-grounded answer for Conv AI / UI (requires a quarantine_id)."""
    if not quarantine_id:
        return (
            "No quarantine_id provided. Open a quarantine in the UI or pass quarantine_id."
        )
    from gaslit.agents.forensic_auditor import answer_qa

    return answer_qa(question, quarantine_id)
