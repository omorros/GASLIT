"""Integration hooks: voice path → Scribe + Forensic Auditor."""

from __future__ import annotations

import hashlib


_CANONICAL_ROOM_IDS = {
    # The attacker line should land in the same user/thread as the seeded MINJA
    # corpus so voice and text attack paths feed the same forensic story.
    "attacker_room": ("u_2188", "t_8821"),
}


def _normalise_room(room: str | None) -> str:
    return (room or "voice").strip().replace(" ", "_") or "voice"


def _stable_voice_turn_number(room: str | None, transcript: str) -> int:
    normalised_transcript = " ".join((transcript or "").strip().split()).lower()
    digest = hashlib.sha256(
        f"{_normalise_room(room)}|{normalised_transcript}".encode("utf-8")
    ).hexdigest()
    return int(digest[:8], 16) + 1


def _voice_ids(room: str | None, transcript: str) -> tuple[str, str, int]:
    r = _normalise_room(room)
    user_id, thread_id = _CANONICAL_ROOM_IDS.get(r, (f"voice:{r}", f"thread:{r}"))
    return user_id, thread_id, _stable_voice_turn_number(r, transcript)


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
