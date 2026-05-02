"""Fallback Sentinel — minimal-viable drift detector.

INSURANCE only. Teammate 1 owns the production Sentinel (Nemotron + LangGraph +
NeMo Guardrails + AWS). If that path slips, this fallback keeps the
FIRED-vs-BLOCKED divergence alive — PRD §15 declares that divergence
non-negotiable.

What this DOES (the load-bearing minimum):
  * Subscribe to `retrieval_log` Change Stream.
  * Compute cohort variance over the last 50 query embeddings for each memory.
  * Update memories.{drift_score, cohort_variance, retrieval_count}.
  * When drift_score > 0.62: write a quarantine doc (idempotent on memory_id +
    drift_bucket) — the WS bridge picks it up and the dossier slides in via
    the Forensic Auditor's Change Stream watcher.

What this DOES NOT do (Teammate 1's job):
  * Nemotron explanation generation
  * NeMo Guardrails wrapping
  * LangGraph checkpointing (no kill-restart)
  * AWS hosting

Run:
  python -m gaslit.agents.sentinel_fallback
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Make the repo importable when run as a module/script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from gaslit.schemas import (
    MEMORIES, RETRIEVAL_LOG, QUARANTINE, DB_NAME, DRIFT_THRESHOLD,
    QUARANTINE_TTL_SECONDS,
)

load_dotenv()

# Calibration constants — match thresholds.json.
BASELINE_VAR = 0.02
P99_VAR = 0.0512


def _client() -> MongoClient:
    return MongoClient(os.environ["MONGODB_URI"])


def compute_drift(db, memory_id: str) -> tuple[float, float, int]:
    """Returns (drift_score in [0,1], cohort_variance_ratio_over_baseline, n_retrievals)."""
    logs = list(
        db[RETRIEVAL_LOG]
        .find({"memory_id": memory_id}, {"query_embedding": 1, "ts": 1, "_id": 0})
        .sort("ts", -1)
        .limit(50)
    )
    n = len(logs)
    if n < 3:
        return 0.0, 0.0, n

    embs = np.array([l["query_embedding"] for l in logs], dtype=np.float32)
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    embs = embs / norms
    sims = embs @ embs.T
    triu = sims[np.triu_indices(n, k=1)]
    cohort_var = float(np.var(triu))

    # Normalize variance to [0,1]: scale so that p99 baseline maps to ~1.0.
    norm_var = min(1.0, cohort_var / P99_VAR)
    var_ratio = cohort_var / BASELINE_VAR if BASELINE_VAR > 0 else 0.0

    # Frequency-vs-age anomaly proxy: many retrievals across diverse queries.
    freq_anomaly = min(1.0, (n / 50.0) * float(1.0 - sims.mean()))

    drift = 0.6 * norm_var + 0.4 * freq_anomaly
    return min(1.0, drift), var_ratio, n


def write_quarantine(db, memory_id: str, drift: float, var: float,
                     sentinel_run_id: str) -> bool:
    """Idempotent. Returns True if a new quarantine doc was created."""
    drift_bucket = round(drift, 1)
    qid = f"q_{memory_id}_{drift_bucket}_{sentinel_run_id}"
    memory = db[MEMORIES].find_one({"memory_id": memory_id}, {"user_id": 1, "_id": 0})
    if not memory:
        return False

    now = datetime.now(timezone.utc)
    doc = {
        "quarantine_id": qid,
        "memory_id": memory_id,
        "quarantined_at": now,
        "drift_score": drift,
        "cohort_variance": var,
        "expires_at": now + timedelta(seconds=QUARANTINE_TTL_SECONDS),
        "responsible_user": memory.get("user_id"),
        "sentinel_run_id": sentinel_run_id,
        "investigation_id": f"inv_{uuid.uuid4().hex[:6]}",
        "siblings_found": [],
        "dossier_text": "",
    }
    try:
        db[QUARANTINE].insert_one(doc)
    except DuplicateKeyError:
        return False
    db[MEMORIES].update_one(
        {"memory_id": memory_id},
        {"$set": {
            "quarantined": True,
            "drift_score": drift,
            "cohort_variance": var,
        }},
    )
    return True


def watch() -> None:
    sentinel_run_id = uuid.uuid4().hex[:8]
    print(f"[sentinel-fallback] run_id={sentinel_run_id} watching {RETRIEVAL_LOG}...",
          flush=True)
    db = _client()[DB_NAME]
    pipeline = [{"$match": {"operationType": "insert"}}]
    last_eval: dict[str, float] = {}
    EVAL_DEBOUNCE_S = 0.5

    while True:
        try:
            with db[RETRIEVAL_LOG].watch(pipeline) as stream:
                for change in stream:
                    doc = change.get("fullDocument") or {}
                    mid = doc.get("memory_id")
                    if not mid:
                        continue
                    now = time.time()
                    if mid in last_eval and now - last_eval[mid] < EVAL_DEBOUNCE_S:
                        continue
                    last_eval[mid] = now

                    drift, var, n = compute_drift(db, mid)
                    db[MEMORIES].update_one(
                        {"memory_id": mid},
                        {"$set": {
                            "drift_score": drift,
                            "cohort_variance": var,
                            "retrieval_count": n,
                        }},
                    )
                    if drift > DRIFT_THRESHOLD:
                        if write_quarantine(db, mid, drift, var, sentinel_run_id):
                            print(
                                f"[sentinel-fallback] QUARANTINED {mid} "
                                f"drift={drift:.2f} variance_ratio={var:.2f} n={n}",
                                flush=True,
                            )
        except Exception as e:
            print(f"[sentinel-fallback] stream error: {type(e).__name__}: {e}; "
                  "restarting in 2s", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    watch()
