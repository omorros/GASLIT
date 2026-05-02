"""ElevenLabs Flash v2.5 TTS — multi-persona narrator/adversary/forensic (PRD §18 +
Operator Console showpiece extension)."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

# PRD constants
DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # forensic auditor (Adam)
DEFAULT_MODEL_ID = "eleven_flash_v2_5"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"

# Sensible default voice IDs (publicly available ElevenLabs voices).
# Operators can override per-persona via env vars below.
# - adversary: a darker/menacing male voice for the MINJA implant line
# - narrator:  calm announcer for live event narration
# - forensic:  existing Adam (PRD locked)
_PERSONA_FALLBACKS = {
    "adversary": "ErXwobaYiN019PkySvjV",  # "Antoni" — public preset, lower register
    "narrator": "21m00Tcm4TlvDq8ikWAM",   # "Rachel" — calm announcer
    "forensic": DEFAULT_VOICE_ID,
}

Persona = Literal["adversary", "narrator", "forensic"]


@lru_cache(maxsize=1)
def _client():
    from elevenlabs import ElevenLabs

    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    return ElevenLabs(api_key=key)


def _resolve_voice_id(persona: str) -> str:
    """Map persona → voice id from env (falling back to public defaults)."""
    persona = persona.lower().strip() if persona else "forensic"
    env_map = {
        "adversary": ("ELEVENLABS_VOICE_ADVERSARY",),
        "narrator": ("ELEVENLABS_VOICE_NARRATOR",),
        "forensic": ("ELEVENLABS_VOICE_FORENSIC", "ELEVENLABS_VOICE_ID"),
    }
    keys = env_map.get(persona, env_map["forensic"])
    for k in keys:
        v = os.environ.get(k, "").strip()
        if v:
            return v
    return _PERSONA_FALLBACKS.get(persona, DEFAULT_VOICE_ID)


def synthesize(text: str, persona: Persona = "forensic") -> bytes:
    """Synthesize speech for `persona`; returns MP3 bytes (mp3_44100_128 by default)."""
    if not text.strip():
        return b""
    client = _client()
    voice_id = _resolve_voice_id(persona)
    model_id = (
        os.environ.get("ELEVENLABS_TTS_MODEL")
        or os.environ.get("ELEVENLABS_MODEL_ID")
        or DEFAULT_MODEL_ID
    )
    output_format = os.environ.get("ELEVENLABS_TTS_OUTPUT_FORMAT", DEFAULT_OUTPUT_FORMAT)

    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id=model_id,
        output_format=output_format,
    )
    return b"".join(audio)


def speak_dossier(text: str) -> bytes:
    """PRD-locked dossier readout (forensic persona). Backward-compatible alias."""
    return synthesize(text, persona="forensic")
