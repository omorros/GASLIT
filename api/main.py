"""GASLIT FastAPI orchestrator — single seam, single merge file.

Owned by Oriol per TEAM_PLAN. Other teammates ship `APIRouter`s that get
include_router'd here:

- Teammate 1: gaslit.agents.sentinel.sentinel_router  (kill / start)
- Teammate 2: gaslit.voice.router.voice_router        (voice-input / forensic-qa)

PRD §13 Dev A. Routes owned by this file:

  POST /api/unprotected-agent
  POST /api/gaslit-agent
  GET  /api/memories
  GET  /api/trust-score
  GET  /health
"""
from __future__ import annotations

# ─── Load env first (repo root + frontend/.env.local) before any project imports ─
import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _env_path in (
    _REPO_ROOT / "frontend" / ".env.local",
    _REPO_ROOT / ".env",
    _REPO_ROOT / ".env.local",
):
    if _env_path.is_file():
        load_dotenv(_env_path, override=True)

import threading
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient

from gaslit.agents.scribe import scribe_turn
from gaslit.retrieval.librarian import (
    retrieve_with_audit, retrieve_unprotected,
)
from gaslit.retrieval.contracts import seed_demo_contracts
from gaslit.schemas import (
    MEMORIES, QUARANTINE, RETRIEVAL_LOG, DB_NAME,
    bootstrap_collections, seed_agent_registry,
)

app = FastAPI(title="GASLIT", version="0.1.0", description="Belief-layer defence on MongoDB Atlas")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_mongo: Optional[MongoClient] = None


def _client() -> MongoClient:
    global _mongo
    if _mongo is None:
        _mongo = MongoClient(os.environ["MONGODB_URI"])
    return _mongo


def _db():
    return _client()[DB_NAME]


# ─── Startup ──────────────────────────────────────────────────────────
@app.on_event("startup")
def _startup():
    """Best-effort startup. Collections + indexes already exist from setup_indexes.py
    so we don't fail the whole API if a transient Atlas blip happens here."""
    try:
        db = _db()
        bootstrap_collections(db)
        seed_agent_registry(db)
        seed_demo_contracts(db)
        print("[api] startup complete; collections + registry + contracts ready")
    except Exception as e:
        print(f"[api] startup bootstrap warning (continuing): {type(e).__name__}: {e}")

    # Forensic Auditor Change Stream watcher (background thread).
    if os.environ.get("FORENSIC_WATCHER", "1") == "1":
        try:
            from gaslit.agents.forensic_auditor import watch_quarantine_stream
            t = threading.Thread(target=watch_quarantine_stream, daemon=True,
                                 name="forensic-watcher")
            t.start()
            print("[api] forensic auditor change-stream watcher started")
        except Exception as e:
            print(f"[api] forensic watcher failed to start: {e}")


# ─── Models ───────────────────────────────────────────────────────────
class AgentRequest(BaseModel):
    message: str
    user_id: str
    thread_id: str
    turn_number: int = 1
    tool_name: Optional[str] = None  # if absent, inferred from message


class AgentResponse(BaseModel):
    response: str
    retrieved_memories: list[dict] = Field(default_factory=list)
    filtered_memories: list[dict] = Field(default_factory=list)
    tool_calls: list[dict] = Field(default_factory=list)
    contract_applied: Optional[str] = None
    agent_id: str


# ─── Tool inference (intentionally simple — deterministic for the demo) ─
def infer_tool(message: str) -> str:
    m = message.lower()
    if "refund" in m and any(s in m for s in ["$", "process", "issue", "approve"]):
        return "refund_request"
    if "transfer" in m or "wire" in m:
        return "transfer_funds"
    if "delete" in m and "account" in m:
        return "delete_account"
    if "send" in m and ("email" in m or "external" in m):
        return "send_email"
    if "balance" in m:
        return "get_balance"
    if "order" in m:
        return "lookup_order"
    return "lookup_order"


def _strip(memory: dict) -> dict:
    return {k: v for k, v in memory.items() if k not in ("_id", "embedding")}


def _looks_like_auto_approval(memories: list[dict]) -> bool:
    for m in memories:
        txt = (m.get("source_text") or "").lower()
        if ("auto-approved" in txt or "auto approved" in txt or
            "automatically approved" in txt):
            return True
    return False


# ─── Endpoints ────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@app.post("/api/unprotected-agent", response_model=AgentResponse)
def unprotected_agent(req: AgentRequest):
    tool_name = req.tool_name or infer_tool(req.message)

    # Best-effort scribe; never blocks the chat path.
    scribe_turn(req.user_id, req.thread_id, req.turn_number, req.message)

    memories = retrieve_unprotected(
        req.message,
        {"tool_name": tool_name, "user_id": None, "agent_id": "unprotected"},
    )

    fired = (tool_name == "refund_request" and _looks_like_auto_approval(memories))
    response = (
        "Processed your refund. You should see it in 3-5 business days."
        if fired else f"Got it: {req.message[:80]}"
    )
    tool_calls = [{"tool": "refund_request", "amount": 4800}] if fired else []
    return AgentResponse(
        response=response,
        retrieved_memories=[_strip(m) for m in memories],
        tool_calls=tool_calls,
        agent_id="unprotected",
    )


@app.post("/api/gaslit-agent", response_model=AgentResponse)
def gaslit_agent(req: AgentRequest):
    tool_name = req.tool_name or infer_tool(req.message)

    scribe_turn(req.user_id, req.thread_id, req.turn_number, req.message)

    audit = retrieve_with_audit(
        req.message,
        {"tool_name": tool_name, "user_id": None, "agent_id": "librarian"},
    )

    fired = (tool_name == "refund_request"
             and _looks_like_auto_approval(audit["memories"]))
    if tool_name == "refund_request" and not fired:
        response = "I'll need to escalate this to a manager."
    elif fired:
        response = "Processed your refund. You should see it in 3-5 business days."
    else:
        response = f"Got it: {req.message[:80]}"

    tool_calls = [{"tool": "refund_request", "amount": 4800}] if fired else []
    return AgentResponse(
        response=response,
        retrieved_memories=[_strip(m) for m in audit["memories"]],
        filtered_memories=audit["filtered"],
        tool_calls=tool_calls,
        contract_applied=audit["contract"]["contract_id"],
        agent_id="gaslit",
    )


@app.get("/api/memories")
def get_memories(limit: int = Query(50, ge=1, le=500)):
    cursor = _db()[MEMORIES].find(
        {}, {"embedding": 0, "_id": 0},
    ).sort("written_at", -1).limit(limit)
    return list(cursor)


@app.get("/api/trust-score")
def trust_score():
    """100 * (1 - mean(drift_score over last 50 memories)). Clamped 0..100."""
    db = _db()
    recent = list(db[MEMORIES].find(
        {}, {"drift_score": 1, "_id": 0},
    ).sort("written_at", -1).limit(50))
    drifts = [d.get("drift_score", 0.0) for d in recent]
    if not drifts:
        score = 100
    else:
        avg = sum(drifts) / len(drifts)
        score = max(0, min(100, int(round(100 * (1 - avg)))))
    n = db[MEMORIES].count_documents({})
    n_q = db[MEMORIES].count_documents({"quarantined": True})
    return {
        "score": score,
        "n_memories": n,
        "n_quarantined": n_q,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# ─── Optional routers from teammates / sibling modules ────────────────
def _try_include(import_path: str, attr: str = "router") -> bool:
    try:
        module = __import__(import_path, fromlist=[attr])
        router = getattr(module, attr)
        app.include_router(router)
        print(f"[api] mounted router from {import_path}")
        return True
    except (ImportError, AttributeError) as e:
        print(f"[api] router {import_path} not mounted ({type(e).__name__})")
        return False


_try_include("gaslit.adversary.minja_simulator", "router")
_try_include("api.compliance_export", "router")
_try_include("gaslit.agents.sentinel", "sentinel_router")
_try_include("gaslit.voice.router", "voice_router")
