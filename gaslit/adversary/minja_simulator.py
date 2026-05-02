"""MINJA attack simulator — runs the canonical 3-turn bridging-steps sequence
from `gaslit/adversary/minja_canonical.json` against the live agents.

Exposes:
  GET  /api/minja-canonical            — frontend fetches narration once
  POST /api/launch-minja-attack        — fire-and-forget; spawns a worker thread
  GET  /api/minja-attack/{attack_id}   — poll progress

Each turn POSTs the same message to BOTH `/api/unprotected-agent` AND
`/api/gaslit-agent` so the dual-pane UI shows the divergence at turn 3.

PRD §12.1.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

CANONICAL_PATH = Path(__file__).parent / "minja_canonical.json"
ATTACK_STATE: dict[str, dict] = {}

router = APIRouter()


def _load_canonical() -> dict:
    return json.loads(CANONICAL_PATH.read_text())


@router.get("/api/minja-canonical")
def get_canonical() -> dict:
    """Frontend uses this to render per-step narration overlays."""
    return _load_canonical()


class MinjaRequest(BaseModel):
    narration_delay_ms: int = 1500


class MinjaResponse(BaseModel):
    attack_id: str
    status: str
    turns: int


@router.post("/api/launch-minja-attack", status_code=202, response_model=MinjaResponse)
def launch_attack(req: MinjaRequest = MinjaRequest()) -> MinjaResponse:
    canonical = _load_canonical()
    attack_id = f"atk_{uuid.uuid4().hex[:8]}"
    ATTACK_STATE[attack_id] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "current_turn": 0,
        "n_turns": len(canonical["turns"]),
    }
    threading.Thread(
        target=_run_attack,
        args=(attack_id, canonical, req.narration_delay_ms),
        daemon=True,
        name=f"minja-{attack_id}",
    ).start()
    return MinjaResponse(
        attack_id=attack_id,
        status="started",
        turns=len(canonical["turns"]),
    )


@router.get("/api/minja-attack/{attack_id}")
def attack_status(attack_id: str) -> dict:
    return ATTACK_STATE.get(attack_id, {"status": "unknown"})


def _run_attack(attack_id: str, canonical: dict, delay_ms: int) -> None:
    api_base = f"http://127.0.0.1:{os.environ.get('API_PORT', '8000')}"
    turns = canonical["turns"]
    thread_id = f"t_minja_{attack_id}"
    try:
        with httpx.Client(base_url=api_base, timeout=30.0) as client:
            for turn in turns:
                ATTACK_STATE[attack_id]["current_turn"] = turn["turn"]
                payload = {
                    "message": turn["user_message"],
                    "user_id": turn["actor"],
                    "thread_id": thread_id,
                    "turn_number": turn["turn"],
                }
                client.post("/api/unprotected-agent", json=payload)
                client.post("/api/gaslit-agent", json=payload)
                time.sleep(delay_ms / 1000.0)
        ATTACK_STATE[attack_id]["status"] = "completed"
        ATTACK_STATE[attack_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        ATTACK_STATE[attack_id]["status"] = "error"
        ATTACK_STATE[attack_id]["error"] = repr(e)
