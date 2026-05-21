"""Voice routes: LiveKit token, STT transcript ingress, forensic Q&A, dossier TTS.

Mounted by api.main as `gaslit.voice.router.voice_router` (see TEAM_PLAN).
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from gaslit.voice.backend_hooks import on_forensic_question, on_voice_transcript
from gaslit.voice.conv_ai import build_public_config, get_agent_id
from gaslit.voice.livekit_handler import VoiceInputPayload, to_scribe_event
from gaslit.voice.tts import speak_dossier, synthesize

voice_router = APIRouter(prefix="/api", tags=["voice"])


class LiveKitTokenRequest(BaseModel):
    room: str = Field(..., description="attacker_room | forensic_room")
    identity: str = Field(default="gaslit-user", max_length=256)


class ForensicQARequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=16_000)
    quarantine_id: str | None = None


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=64_000)
    persona: str = Field(
        default="forensic",
        description="adversary | narrator | forensic — selects ElevenLabs voice id",
    )


def _livekit_token(*, room: str, identity: str) -> tuple[str, str]:
    from livekit import api

    key = os.environ.get("LIVEKIT_API_KEY")
    secret = os.environ.get("LIVEKIT_API_SECRET")
    if not key or not secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "LIVEKIT_API_KEY / LIVEKIT_API_SECRET not configured. "
                "Set them in repo-root .env (same folder as api/), restart uvicorn. "
                "Check GET /api/voice/env-status for booleans."
            ),
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
        raise HTTPException(
            status_code=503,
            detail="LIVEKIT_URL not configured in repo-root .env — restart uvicorn after fixing.",
        )
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
        source=event["source"],
        user_id=event["user_id"],
        thread_id=event["thread_id"],
        turn_number=event["turn_number"],
    )
    return JSONResponse(result)


@voice_router.post("/forensic-qa")
async def forensic_qa(body: ForensicQARequest) -> JSONResponse:
    """Transcribed question → Forensic Auditor (stub) → text for UI / Conv AI."""
    answer = await on_forensic_question(body.question, body.quarantine_id)
    return JSONResponse({"answer": answer, "quarantine_id": body.quarantine_id})


_VALID_PERSONAS = {"adversary", "narrator", "forensic"}


@voice_router.post("/voice/tts")
async def voice_tts(body: TTSRequest) -> Response:
    """ElevenLabs Flash v2.5 — multi-persona TTS for the Operator Console.

    `persona` selects which voice id to use:
    - adversary: ELEVENLABS_VOICE_ADVERSARY (default Antoni)
    - narrator:  ELEVENLABS_VOICE_NARRATOR (default Rachel)
    - forensic:  ELEVENLABS_VOICE_FORENSIC | ELEVENLABS_VOICE_ID (default Adam, PRD-locked)
    """
    persona = body.persona.lower().strip() if body.persona else "forensic"
    if persona not in _VALID_PERSONAS:
        persona = "forensic"
    try:
        if persona == "forensic":
            mp3 = speak_dossier(body.text)
        else:
            mp3 = synthesize(body.text, persona=persona)  # type: ignore[arg-type]
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TTS failed: {e!s}") from e
    return Response(
        content=mp3,
        media_type="audio/mpeg",
        headers={"X-GASLIT-Persona": persona},
    )


@voice_router.get("/voice/convai-config")
async def convai_public_config() -> JSONResponse:
    """Non-secret Conv AI widget hints for the frontend."""
    return JSONResponse(build_public_config())


@voice_router.get("/voice/env-status")
async def voice_env_status() -> JSONResponse:
    """Which voice-related env vars the API process sees (booleans only — no secrets)."""
    return JSONResponse(
        {
            "repo_root_env_hint": "Put LIVEKIT_* and ELEVENLABS_* in repo-root .env (not only frontend/.env.local). Restart uvicorn after editing.",
            "LIVEKIT_URL": bool(os.environ.get("LIVEKIT_URL", "").strip()),
            "LIVEKIT_API_KEY": bool(os.environ.get("LIVEKIT_API_KEY", "").strip()),
            "LIVEKIT_API_SECRET": bool(os.environ.get("LIVEKIT_API_SECRET", "").strip()),
            "ELEVENLABS_API_KEY": bool(os.environ.get("ELEVENLABS_API_KEY", "").strip()),
            "ELEVENLABS_AGENT_ID": bool((get_agent_id() or "").strip()),
        }
    )
