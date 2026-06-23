"""Integration hooks: voice path → Scribe + Forensic Auditor."""

from __future__ import annotations

import hashlib
import re


def _voice_ids(room: str | None) -> tuple[str, str, int]:
    r = (room or "voice").strip().replace(" ", "_") or "voice"
    if r == "attacker_room":
        return "u_2188", "t_8821", 1
    return f"voice:{r}", f"thread:{r}", 1


def _stable_turn_number(room: str | None, transcript: str) -> int:
    normalized = re.sub(r"\s+", " ", transcript.strip().lower())
    seed = f"{room or 'voice'}|{normalized}".encode()
    # Keep turn numbers deterministic so duplicate final STT deliveries are idempotent,
    # while distinct utterances in the same room no longer overwrite turn 1.
    return int(hashlib.sha256(seed).hexdigest()[:8], 16) % 900_000 + 1


async def on_voice_transcript(transcript: str, room: str | None, source: str | None) -> dict:
    """Forward speech-as-text into the Scribe memory pipeline."""
    from gaslit.agents.scribe import scribe_turn

    user_id, thread_id, _ = _voice_ids(room)
    turn_number = _stable_turn_number(room, transcript)
    mem = scribe_turn(user_id, thread_id, turn_number, transcript)
    return {
        "ok": True,
        "accepted": mem is not None,
        "transcript": transcript,
        "room": room,
        "source": source,
        "user_id": user_id,
        "thread_id": thread_id,
        "turn_number": turn_number,
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
