"""Integration hooks: voice path → Scribe + Forensic Auditor."""

from __future__ import annotations

import hashlib
import re

_CANONICAL_ROOM_IDS: dict[str, tuple[str, str]] = {
    # The attacker room is the spoken version of the canonical MINJA actor.
    "attacker_room": ("u_2188", "t_8821"),
}


def _room_key(room: str | None) -> str:
    raw = (room or "voice").strip().lower()
    key = re.sub(r"[^a-z0-9_.:-]+", "_", raw).strip("_")
    return key or "voice"


def _stable_voice_turn(room_key: str, transcript: str) -> int:
    normalized = " ".join(transcript.strip().lower().split())
    digest = hashlib.sha256(f"{room_key}|{normalized}".encode()).hexdigest()
    return int(digest[:8], 16) + 1


def _voice_ids(room: str | None, transcript: str) -> tuple[str, str, int]:
    room_key = _room_key(room)
    user_id, thread_id = _CANONICAL_ROOM_IDS.get(
        room_key,
        (f"voice:{room_key}", f"thread:{room_key}"),
    )
    return user_id, thread_id, _stable_voice_turn(room_key, transcript)


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
