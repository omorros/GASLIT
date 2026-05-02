"""WebSocket bridge — Atlas Change Streams to browser clients.

Subscribes to:
  memories         (updates → drift_update)
  retrieval_log    (inserts → retrieval)
  quarantine       (inserts → quarantine)

Broadcasts JSON envelopes per docs/contracts.md §1 to every client connected on
ws://0.0.0.0:WS_PORT (default 8001).

Run:
  python ws/bridge.py

Resilient: each watcher catches and restarts its own stream on failure.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Make the repo importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

import websockets

from gaslit.schemas import (
    MEMORIES, RETRIEVAL_LOG, QUARANTINE, DB_NAME, DRIFT_THRESHOLD,
)

load_dotenv()

CLIENTS: set = set()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _envelope(event_type: str, payload: dict) -> str:
    return json.dumps(
        {"type": event_type, "payload": payload, "ts": _now_iso()},
        default=str,
    )


async def broadcast(event_type: str, payload: dict) -> None:
    if not CLIENTS:
        return
    msg = _envelope(event_type, payload)
    coros = [c.send(msg) for c in list(CLIENTS)]
    await asyncio.gather(*coros, return_exceptions=True)


async def handler(ws):
    CLIENTS.add(ws)
    try:
        await ws.send(_envelope("agent_status", {
            "agent_id": "ws-bridge", "status": "online",
        }))
        async for _ in ws:
            pass  # broadcast-only
    finally:
        CLIENTS.discard(ws)


# ─── Watchers ─────────────────────────────────────────────────────────
async def watch_memories(db) -> None:
    pipeline = [{"$match": {"operationType": {"$in": ["update", "replace", "insert"]}}}]
    while True:
        try:
            async with db[MEMORIES].watch(pipeline, full_document="updateLookup") as stream:
                async for change in stream:
                    doc = change.get("fullDocument") or {}
                    if not doc.get("memory_id"):
                        continue
                    drift = float(doc.get("drift_score", 0.0))
                    await broadcast("drift_update", {
                        "memory_id": doc["memory_id"],
                        "drift_score": drift,
                        "cohort_variance": float(doc.get("cohort_variance", 0.0)),
                        "retrieval_count": int(doc.get("retrieval_count", 0)),
                        "above_threshold": drift > DRIFT_THRESHOLD,
                    })
        except Exception as e:
            print(f"[ws-bridge] memories watcher error: {e!r}; restarting in 2s")
            await asyncio.sleep(2)


async def watch_retrieval_log(db) -> None:
    pipeline = [{"$match": {"operationType": "insert"}}]
    while True:
        try:
            async with db[RETRIEVAL_LOG].watch(pipeline) as stream:
                async for change in stream:
                    doc = change.get("fullDocument") or {}
                    await broadcast("retrieval", {
                        "memory_id": doc.get("memory_id"),
                        "agent_id": doc.get("agent_id"),
                        "contract_id": doc.get("contract_id"),
                        "retrieved_rank": doc.get("retrieved_rank"),
                        "score": doc.get("score"),
                        "filtered": bool(doc.get("filtered", False)),
                    })
        except Exception as e:
            print(f"[ws-bridge] retrieval_log watcher error: {e!r}; restarting in 2s")
            await asyncio.sleep(2)


async def watch_quarantine(db) -> None:
    pipeline = [{"$match": {"operationType": {"$in": ["insert", "update"]}}}]
    while True:
        try:
            async with db[QUARANTINE].watch(pipeline, full_document="updateLookup") as stream:
                async for change in stream:
                    doc = change.get("fullDocument") or {}
                    if not doc.get("quarantine_id"):
                        continue
                    await broadcast("quarantine", {
                        "quarantine_id": doc["quarantine_id"],
                        "memory_id": doc.get("memory_id"),
                        "drift_score": doc.get("drift_score"),
                        "cohort_variance": doc.get("cohort_variance"),
                        "responsible_user": doc.get("responsible_user"),
                        "siblings_found": doc.get("siblings_found", []),
                        "dossier_text": doc.get("dossier_text", ""),
                        "investigation_id": doc.get("investigation_id"),
                    })
        except Exception as e:
            print(f"[ws-bridge] quarantine watcher error: {e!r}; restarting in 2s")
            await asyncio.sleep(2)


# ─── Main ─────────────────────────────────────────────────────────────
async def main() -> None:
    port = int(os.environ.get("WS_PORT", "8001"))
    uri = os.environ["MONGODB_URI"]
    client = AsyncIOMotorClient(uri)
    db = client[DB_NAME]

    print(f"[ws-bridge] starting on ws://0.0.0.0:{port}")
    server = await websockets.serve(handler, "0.0.0.0", port)

    await asyncio.gather(
        server.wait_closed(),
        watch_memories(db),
        watch_retrieval_log(db),
        watch_quarantine(db),
    )


if __name__ == "__main__":
    asyncio.run(main())
