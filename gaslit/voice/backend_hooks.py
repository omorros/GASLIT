"""Integration hooks: voice path → Scribe + Forensic Auditor."""

from __future__ import annotations

import hashlib


def _normalize_transcript(transcript: str) -> str:
    return " ".join((transcript or "").casefold().split())


def _stable_turn_number(room: str | None, transcript: str) -> int:
    normalized = _normalize_transcript(transcript)
    basis = f"{room or 'voice'}|{normalized}"
    return int(hashlib.sha256(basis.encode()).hexdigest()[:8], 16) + 1


def _voice_ids(room: str | None, transcript: str = "") -> tuple[str, str, int]:
    r = (room or "voice").replace(" ", "_")
    if r == "attacker_room":
        user_id, thread_id = "u_2188", "t_8821"
    else:
        user_id, thread_id = f"voice:{r}", f"thread:{r}"
    return user_id, thread_id, _stable_turn_number(r, transcript)


async def on_voice_transcript(transcript: str, room: str | None, source: str | None) -> dict:
    """Forward speech-as-text into the Scribe memory pipeline."""
    from gaslit.agents.scribe import scribe_turn

    user_id, thread_id, turn_number = _voice_ids(room, transcript)
    mem = scribe_turn(user_id, thread_id, turn_number, transcript)
    return {
        "ok": True,
        "accepted": bool((mem or {}).get("memory_id")),
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
