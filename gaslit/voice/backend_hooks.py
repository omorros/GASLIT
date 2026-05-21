"""Integration hooks: voice path → Scribe + Forensic Auditor."""

from __future__ import annotations

import hashlib
import re

_ROOM_DEFAULTS = {
    # Contracted attacker-room voice implant should land in the MINJA demo identity.
    "attacker_room": ("u_2188", "t_8821"),
}


def _room_key(room: str | None) -> str:
    key = re.sub(r"[^A-Za-z0-9_.:-]+", "_", (room or "voice").strip())
    return key.strip("_") or "voice"


def _voice_turn_number(room_key: str, transcript: str) -> int:
    normalized = " ".join(transcript.strip().split())
    digest = hashlib.sha256(f"{room_key}|{normalized}".encode()).hexdigest()
    return int(digest[:12], 16)


def _voice_ids(
    room: str | None,
    transcript: str,
    user_id: str | None = None,
    thread_id: str | None = None,
    turn_number: int | None = None,
) -> tuple[str, str, int]:
    room_key = _room_key(room)
    default_user_id, default_thread_id = _ROOM_DEFAULTS.get(
        room_key,
        (f"voice:{room_key}", f"thread:{room_key}"),
    )
    return (
        user_id or default_user_id,
        thread_id or default_thread_id,
        turn_number if turn_number is not None else _voice_turn_number(room_key, transcript),
    )


async def on_voice_transcript(
    transcript: str,
    room: str | None,
    source: str | None,
    user_id: str | None = None,
    thread_id: str | None = None,
    turn_number: int | None = None,
) -> dict:
    """Forward speech-as-text into the Scribe memory pipeline."""
    from gaslit.agents.scribe import scribe_turn

    scribe_user_id, scribe_thread_id, scribe_turn_number = _voice_ids(
        room,
        transcript,
        user_id=user_id,
        thread_id=thread_id,
        turn_number=turn_number,
    )
    mem = scribe_turn(scribe_user_id, scribe_thread_id, scribe_turn_number, transcript)
    return {
        "ok": True,
        "accepted": mem is not None,
        "transcript": transcript,
        "room": room,
        "source": source,
        "user_id": scribe_user_id,
        "thread_id": scribe_thread_id,
        "turn_number": scribe_turn_number,
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
