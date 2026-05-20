"""GASLIT Sentinel — production LangGraph drift agent (Teammate 1).

Architecture
------------

The Sentinel is the only non-Oriol-owned agent. It watches the
``retrieval_log`` Change Stream, scores drift per memory, and emits
quarantine events when ``drift_score > 0.62``. The graph is checkpointed
to MongoDB (``langgraph_checkpoints`` / ``langgraph_checkpoint_writes``)
so ``kill_sentinel`` → ``start_sentinel`` resumes cleanly.

This module ships TWO surfaces:

1. ``main()`` — long-running process entrypoint. ECS Fargate + local shell
   invocation both use ``python -m gaslit.agents.sentinel``.
2. ``sentinel_router`` — FastAPI ``APIRouter`` mounted by ``api/main.py``
   at ``/api/kill-sentinel`` and ``/api/start-sentinel``.

Deployment modes (via ``SENTINEL_MODE`` env var)
------------------------------------------------

* ``local``  (default) — kill/start manage a background thread in the API
  process.
* ``ecs``    — kill/start call ``boto3 ecs.update_service`` on the service
  identified by ``ECS_CLUSTER`` + ``ECS_SERVICE``.

The graph itself is identical in both modes; only the lifecycle control
plane differs.

Idempotency
-----------

The quarantine write key is ``(memory_id, drift_bucket, sentinel_run_id)``,
exposed via the ``quarantine_id`` unique index. A single drift crossing
therefore produces exactly one quarantine document, even if the Change
Stream redelivers the same retrieval.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, TypedDict

# Make the repo importable when run as ``python -m gaslit.agents.sentinel``
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph import END, START, StateGraph

from gaslit.agents.sentinel_fallback import compute_drift
from gaslit.agents.eval_debounce import PendingEval, due_memory_ids, schedule_eval
from gaslit.agents.sentinel_nemotron import explain_drift
from gaslit.schemas import (
    AGENT_REGISTRY,
    CHECKPOINTS,
    DB_NAME,
    DRIFT_THRESHOLD,
    MEMORIES,
    QUARANTINE,
    QUARANTINE_TTL_SECONDS,
    RETRIEVAL_LOG,
)

load_dotenv()

log = logging.getLogger("gaslit.sentinel")
logging.basicConfig(
    level=os.environ.get("SENTINEL_LOG_LEVEL", "INFO"),
    format="%(asctime)s [sentinel] %(levelname)s %(message)s",
)

SENTINEL_MODE = os.environ.get("SENTINEL_MODE", "local").lower()


# ─── State ───────────────────────────────────────────────────────────
class SentinelState(TypedDict, total=False):
    memory_id: str
    drift_score: float
    cohort_variance: float
    n_retrievals: int
    quarantine_written: bool
    nemotron_explanation: str
    sentinel_run_id: str
    snippet: str
    user_id: str


# ─── Node implementations ────────────────────────────────────────────
_db_client_cache: Optional[MongoClient] = None


def _client() -> MongoClient:
    global _db_client_cache
    if _db_client_cache is None:
        _db_client_cache = MongoClient(os.environ["MONGODB_URI"])
    return _db_client_cache


def _db():
    return _client()[DB_NAME]


def _compute_drift_node(state: SentinelState) -> SentinelState:
    db = _db()
    mid = state["memory_id"]
    drift, var_ratio, n = compute_drift(db, mid)
    mem = db[MEMORIES].find_one(
        {"memory_id": mid}, {"source_text": 1, "user_id": 1, "_id": 0}
    ) or {}
    db[MEMORIES].update_one(
        {"memory_id": mid},
        {"$set": {
            "drift_score": drift,
            "cohort_variance": var_ratio,
            "retrieval_count": n,
        }},
    )
    return {
        "drift_score": drift,
        "cohort_variance": var_ratio,
        "n_retrievals": n,
        "snippet": (mem.get("source_text") or "")[:240],
        "user_id": mem.get("user_id", ""),
    }


def _should_quarantine(state: SentinelState) -> str:
    if state.get("drift_score", 0.0) > DRIFT_THRESHOLD:
        return "explain"
    return "done"


def _explain_node(state: SentinelState) -> SentinelState:
    """Nemotron (or Haiku fallback) produces the dossier explanation text."""
    try:
        text = explain_drift(
            memory_id=state["memory_id"],
            drift_score=state["drift_score"],
            cohort_variance=state.get("cohort_variance", 0.0),
            snippet=state.get("snippet", ""),
            retrieval_count=state.get("n_retrievals", 0),
        )
    except Exception as exc:
        log.warning("explain_drift failed for %s: %s", state["memory_id"], exc)
        text = (
            f"Drift {state['drift_score']:.2f} > 0.62 for {state['memory_id']} "
            "(explanation pipeline unavailable)."
        )
    return {"nemotron_explanation": text}


def _quarantine_node(state: SentinelState) -> SentinelState:
    """Idempotent quarantine write. Returns quarantine_written flag in state."""
    db = _db()
    mid = state["memory_id"]
    drift = state["drift_score"]
    var = state.get("cohort_variance", 0.0)
    run_id = state["sentinel_run_id"]
    drift_bucket = round(drift, 1)
    qid = f"q_{mid}_{drift_bucket}_{run_id}"

    now = datetime.now(timezone.utc)
    doc = {
        "quarantine_id": qid,
        "memory_id": mid,
        "quarantined_at": now,
        "drift_score": drift,
        "cohort_variance": var,
        "expires_at": now + timedelta(seconds=QUARANTINE_TTL_SECONDS),
        "responsible_user": state.get("user_id", ""),
        "sentinel_run_id": run_id,
        "investigation_id": f"inv_{uuid.uuid4().hex[:6]}",
        "siblings_found": [],
        "dossier_text": state.get("nemotron_explanation", ""),
    }
    written = False
    try:
        db[QUARANTINE].insert_one(doc)
        written = True
    except DuplicateKeyError:
        # Update dossier text if the explanation is richer than a stub.
        if state.get("nemotron_explanation"):
            db[QUARANTINE].update_one(
                {"quarantine_id": qid},
                {"$set": {"dossier_text": state["nemotron_explanation"]}},
            )

    db[MEMORIES].update_one(
        {"memory_id": mid},
        {"$set": {
            "quarantined": True,
            "drift_score": drift,
            "cohort_variance": var,
        }},
    )

    if written:
        log.info("QUARANTINED %s drift=%.2f var=%.2f qid=%s",
                 mid, drift, var, qid)
    return {"quarantine_written": written}


def _done_node(state: SentinelState) -> SentinelState:
    return state


# ─── Graph ───────────────────────────────────────────────────────────
def _build_graph(saver: MongoDBSaver):
    builder = StateGraph(SentinelState)
    builder.add_node("compute_drift", _compute_drift_node)
    builder.add_node("explain", _explain_node)
    builder.add_node("quarantine", _quarantine_node)
    builder.add_node("done", _done_node)

    builder.add_edge(START, "compute_drift")
    builder.add_conditional_edges(
        "compute_drift",
        _should_quarantine,
        {"explain": "explain", "done": "done"},
    )
    builder.add_edge("explain", "quarantine")
    builder.add_edge("quarantine", "done")
    builder.add_edge("done", END)
    return builder.compile(checkpointer=saver)


# ─── Long-running watcher ────────────────────────────────────────────
_stop_event = threading.Event()
_worker_thread: Optional[threading.Thread] = None
_worker_lock = threading.Lock()
_run_id: Optional[str] = None


def _invoke_graph(graph, memory_id: str, run_id: str) -> None:
    thread_id = f"sentinel-{memory_id}"
    config = {"configurable": {"thread_id": thread_id}}
    try:
        graph.invoke(
            {
                "memory_id": memory_id,
                "sentinel_run_id": run_id,
            },
            config=config,
        )
    except Exception as invoke_exc:
        log.warning("graph invoke failed for %s: %s", memory_id, invoke_exc)


def _flush_due_evaluations(
    pending_eval: PendingEval,
    graph,
    run_id: str,
    stop_event: threading.Event,
) -> None:
    for mid in due_memory_ids(pending_eval, time.time()):
        if stop_event.is_set():
            return
        _invoke_graph(graph, mid, run_id)


def _watch_loop(stop_event: threading.Event, run_id: str) -> None:
    client = _client()
    db = client[DB_NAME]

    # MongoDBSaver's collection lives in the main GASLIT DB so the whole
    # state is in one place for the compliance export to bundle later.
    saver = MongoDBSaver(
        client=client,
        db_name=DB_NAME,
        checkpoint_collection_name=CHECKPOINTS,
        writes_collection_name="langgraph_checkpoint_writes",
    )
    graph = _build_graph(saver)

    _register_agent_status(db, "online", run_id=run_id)
    log.info("sentinel watching %s.%s run_id=%s mode=%s",
             DB_NAME, RETRIEVAL_LOG, run_id, SENTINEL_MODE)

    pending_eval: PendingEval = {}
    pipeline = [{"$match": {"operationType": "insert"}}]

    while not stop_event.is_set():
        try:
            with db[RETRIEVAL_LOG].watch(pipeline, max_await_time_ms=200) as stream:
                while not stop_event.is_set():
                    change = stream.try_next()
                    if change is None:
                        _flush_due_evaluations(pending_eval, graph, run_id, stop_event)
                        time.sleep(0.05)
                        continue

                    doc = change.get("fullDocument") or {}
                    mid = doc.get("memory_id")
                    if not mid:
                        continue
                    schedule_eval(pending_eval, mid, time.time())
                    _flush_due_evaluations(pending_eval, graph, run_id, stop_event)
        except Exception as exc:
            if stop_event.is_set():
                break
            log.warning("change-stream error (%s); restarting in 2s",
                        type(exc).__name__)
            time.sleep(2)

    _register_agent_status(db, "offline", run_id=run_id)
    log.info("sentinel loop stopped run_id=%s", run_id)


def _register_agent_status(db, status: str, run_id: str,
                           note: str = "", superstep: Optional[int] = None) -> None:
    """Write agent_status into agent_registry. The bridge polls memories/
    retrieval_log/quarantine; the HTTP router returns status inline, so this
    is primarily a durable record for the compliance export + dashboards.
    """
    payload: dict[str, Any] = {
        "status": status,
        "run_id": run_id,
        "last_status_at": datetime.now(timezone.utc),
    }
    if note:
        payload["note"] = note
    if superstep is not None:
        payload["superstep"] = superstep
    db[AGENT_REGISTRY].update_one(
        {"agent_id": "sentinel"},
        {"$set": payload},
        upsert=True,
    )


def _last_superstep(db) -> int:
    """Count of Sentinel-owned checkpoints — used for the 'resumed at superstep N' UI."""
    return db[CHECKPOINTS].count_documents(
        {"thread_id": {"$regex": "^sentinel-"}},
    )


# ─── Lifecycle (local thread) ────────────────────────────────────────
def start_local() -> dict:
    global _worker_thread, _run_id
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return {
                "status": "already_running",
                "run_id": _run_id,
                "superstep": _last_superstep(_db()),
            }
        _stop_event.clear()
        _run_id = uuid.uuid4().hex[:8]
        _worker_thread = threading.Thread(
            target=_watch_loop,
            args=(_stop_event, _run_id),
            daemon=True,
            name="sentinel-watch",
        )
        _worker_thread.start()
        superstep = _last_superstep(_db())
        return {
            "status": "resumed" if superstep > 0 else "started",
            "run_id": _run_id,
            "superstep": superstep,
            "mode": "local",
        }


def stop_local(timeout_s: float = 3.0) -> dict:
    global _worker_thread
    with _worker_lock:
        if _worker_thread is None or not _worker_thread.is_alive():
            return {"status": "not_running", "superstep": _last_superstep(_db())}
        _stop_event.set()
        _worker_thread.join(timeout=timeout_s)
        superstep = _last_superstep(_db())
        note = "Sentinel offline (local)"
        _register_agent_status(_db(), "offline", run_id=_run_id or "",
                               note=note, superstep=superstep)
        _worker_thread = None
        return {"status": "killed", "superstep": superstep, "mode": "local"}


# ─── Lifecycle (AWS ECS) ─────────────────────────────────────────────
def _ecs_client():
    import boto3
    session = boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE"),
        region_name=os.environ.get("AWS_REGION", "eu-west-2"),
    )
    return session.client("ecs")


def stop_ecs() -> dict:
    cluster = os.environ["ECS_CLUSTER"]
    service = os.environ["ECS_SERVICE"]
    ecs = _ecs_client()
    ecs.update_service(cluster=cluster, service=service, desiredCount=0)
    return {
        "status": "killed",
        "cluster": cluster,
        "service": service,
        "mode": "ecs",
        "superstep": _last_superstep(_db()),
    }


def start_ecs() -> dict:
    cluster = os.environ["ECS_CLUSTER"]
    service = os.environ["ECS_SERVICE"]
    ecs = _ecs_client()
    ecs.update_service(cluster=cluster, service=service, desiredCount=1)
    superstep = _last_superstep(_db())
    return {
        "status": "resumed" if superstep > 0 else "started",
        "cluster": cluster,
        "service": service,
        "mode": "ecs",
        "superstep": superstep,
    }


# ─── FastAPI router ──────────────────────────────────────────────────
sentinel_router = APIRouter()


class SentinelLifecycleResponse(BaseModel):
    status: str
    mode: str = "local"
    run_id: Optional[str] = None
    superstep: Optional[int] = None
    cluster: Optional[str] = None
    service: Optional[str] = None
    note: Optional[str] = None


@sentinel_router.post("/api/kill-sentinel", response_model=SentinelLifecycleResponse)
def api_kill_sentinel() -> SentinelLifecycleResponse:
    try:
        if SENTINEL_MODE == "ecs":
            result = stop_ecs()
        else:
            result = stop_local()
        return SentinelLifecycleResponse(**result)
    except KeyError as exc:
        raise HTTPException(status_code=500,
                            detail=f"missing env var {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@sentinel_router.post("/api/start-sentinel", response_model=SentinelLifecycleResponse)
def api_start_sentinel() -> SentinelLifecycleResponse:
    try:
        if SENTINEL_MODE == "ecs":
            result = start_ecs()
        else:
            result = start_local()
        return SentinelLifecycleResponse(**result)
    except KeyError as exc:
        raise HTTPException(status_code=500,
                            detail=f"missing env var {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@sentinel_router.get("/api/sentinel-status", response_model=SentinelLifecycleResponse)
def api_sentinel_status() -> SentinelLifecycleResponse:
    """Lightweight health probe — used by the dossier component + ECS healthcheck."""
    db = _db()
    doc = db[AGENT_REGISTRY].find_one({"agent_id": "sentinel"}) or {}
    superstep = _last_superstep(db)
    status = doc.get("status", "unknown")
    if SENTINEL_MODE == "local":
        alive = _worker_thread is not None and _worker_thread.is_alive()
        if alive and status != "online":
            status = "online"
        elif not alive and status == "online":
            status = "offline"
    return SentinelLifecycleResponse(
        status=status,
        mode=SENTINEL_MODE,
        run_id=doc.get("run_id"),
        superstep=superstep,
        note=doc.get("note"),
    )


# ─── Process entrypoint ──────────────────────────────────────────────
def main() -> int:
    """Long-running process. Used by ``scripts/start_sentinel.sh`` + ECS.

    SIGTERM / SIGINT → flush checkpoint then exit 0.
    """
    result = start_local()
    log.info("sentinel %s (run_id=%s)", result["status"], result.get("run_id"))

    def _handle(signum, _frame):
        log.info("received signal %d — stopping", signum)
        stop_local()
        log.info("sentinel exit")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    # Block while the watcher thread runs.
    while _worker_thread is not None and _worker_thread.is_alive():
        time.sleep(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
