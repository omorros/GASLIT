"""Voice routes: LiveKit token, STT transcript ingress, forensic Q&A, dossier TTS.

Mounted by api.main as `gaslit.voice.router.voice_router` (see TEAM_PLAN).
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from gaslit.voice.backend_hooks import on_forensic_question, on_voice_transcript
from gaslit.voice.conv_ai import build_public_config
from gaslit.voice.livekit_handler import VoiceInputPayload, to_scribe_event
from gaslit.voice.tts import speak_dossier

voice_router = APIRouter(prefix="/api", tags=["voice"])


class LiveKitTokenRequest(BaseModel):
    room: str = Field(..., description="attacker_room | forensic_room")
    identity: str = Field(default="gaslit-user", max_length=256)


class ForensicQARequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=16_000)
    quarantine_id: str | None = None


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=64_000)


def _livekit_token(*, room: str, identity: str) -> tuple[str, str]:
    from livekit import api

    key = os.environ.get("LIVEKIT_API_KEY")
    secret = os.environ.get("LIVEKIT_API_SECRET")
    if not key or not secret:
        raise HTTPException(
            status_code=503,
            detail="LIVEKIT_API_KEY / LIVEKIT_API_SECRET not configured",
        )

    grants = api.VideoGrants(room_join=True, room=room)
    at = (
        api.AccessToken(key, secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(grants)
    )
    jwt = at.to_jwt()
    url = os.environ.get("LIVEKIT_URL", "")
    if not url:
        raise HTTPException(status_code=503, detail="LIVEKIT_URL not configured")
    return jwt, url


@voice_router.post("/livekit/token")
async def issue_livekit_token(body: LiveKitTokenRequest) -> JSONResponse:
    """Mint a short-lived JWT for the browser to join a LiveKit room."""
    token, url = _livekit_token(room=body.room, identity=body.identity)
    return JSONResponse({"token": token, "url": url, "room": body.room})


@voice_router.post("/voice-input")
async def voice_input(body: VoiceInputPayload) -> JSONResponse:
    """Final transcript from LiveKit (or fallback) → Scribe pipeline."""
    event = to_scribe_event(body)
    result = await on_voice_transcript(
        event["transcript"],
        room=body.room,
        source=body.source,
    )
    return JSONResponse(result)


@voice_router.post("/forensic-qa")
async def forensic_qa(body: ForensicQARequest) -> JSONResponse:
    """Transcribed question → Forensic Auditor (stub) → text for UI / Conv AI."""
    answer = await on_forensic_question(body.question, body.quarantine_id)
    return JSONResponse({"answer": answer, "quarantine_id": body.quarantine_id})


@voice_router.post("/voice/tts")
async def voice_tts(body: TTSRequest) -> Response:
    """ElevenLabs Flash v2.5 — returns audio/mpeg bytes for dossier playback."""
    try:
        mp3 = speak_dossier(body.text)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TTS failed: {e!s}") from e
    return Response(content=mp3, media_type="audio/mpeg")


@voice_router.get("/voice/convai-config")
async def convai_public_config() -> JSONResponse:
    """Non-secret Conv AI widget hints for the frontend."""
    return JSONResponse(build_public_config())
