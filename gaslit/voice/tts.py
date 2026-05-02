"""ElevenLabs Flash v2.5 TTS for forensic dossier readout (PRD §18)."""

from __future__ import annotations

import os
from functools import lru_cache

# PRD constants
DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
DEFAULT_MODEL_ID = "eleven_flash_v2_5"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


@lru_cache(maxsize=1)
def _client():
    from elevenlabs import ElevenLabs

    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    return ElevenLabs(api_key=key)


def speak_dossier(text: str) -> bytes:
    """Synthesize dossier narration; returns MP3 bytes."""
    if not text.strip():
        return b""

    client = _client()
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
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
