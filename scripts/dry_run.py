"""End-to-end demo orchestrator — runs the full setup + integration check.

Usage:
  python scripts/dry_run.py                   # full run
  python scripts/dry_run.py --skip-load       # use what's already in Atlas
  python scripts/dry_run.py --record-replay   # also record events_replay.json
  python scripts/dry_run.py --reset           # wipe + reload from corpus.json

Exit codes:
  0 = green (FIRED+BLOCKED divergence achieved)
  1 = integration check failed
  2 = setup error (missing fixtures, indexes not ready, etc.)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv
from pymongo import MongoClient

from gaslit.schemas import (
    MEMORIES, RETRIEVAL_LOG, QUARANTINE, BELIEF_CONTRACTS, DB_NAME,
    VECTOR_INDEX, TEXT_INDEX,
)

load_dotenv()

PY = str(REPO / ".venv" / "Scripts" / "python.exe")
API_PORT = os.environ.get("API_PORT", "8002")
WS_PORT = os.environ.get("WS_PORT", "8003")
API = f"http://127.0.0.1:{API_PORT}"
WS = f"ws://127.0.0.1:{WS_PORT}"


def step(label: str) -> None:
    print(f"\n[dry_run] {label}", flush=True)


def run_py(*args: str, timeout: int = 600) -> int:
    print(f"  $ {' '.join(args)}", flush=True)
    r = subprocess.run([PY, *args], cwd=str(REPO), timeout=timeout)
    return r.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-load", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--record-replay", action="store_true")
    parser.add_argument("--replay-duration", type=int, default=60)
    args = parser.parse_args()

    db = MongoClient(os.environ["MONGODB_URI"])[DB_NAME]

    step("1. setup_indexes (idempotent)")
    if run_py("scripts/setup_indexes.py") != 0:
        return 2

    if not args.skip_load:
        corpus = REPO / "fixtures" / "corpus.json"
        if not corpus.exists():
            print("  fixtures/corpus.json missing — run scripts/generate_corpus.py first")
            return 2
        step("2. load_baseline_corpus")
        load_args = ["scripts/load_baseline_corpus.py"]
        if args.reset:
            load_args.append("--reset")
        if run_py(*load_args) != 0:
            return 2

    step("3. seed_demo (pre-warm m_4419 to drift=0.58)")
    if run_py("scripts/seed_demo.py") != 0:
        return 2

    step("4. wait for Atlas Search to report READY")
    deadline = time.time() + 300
    while time.time() < deadline:
        memo_idx = {i["name"]: i.get("queryable", False)
                    for i in db[MEMORIES].list_search_indexes()}
        if memo_idx.get(VECTOR_INDEX) and memo_idx.get(TEXT_INDEX):
            print(f"  search indexes READY: {memo_idx}")
            break
        print(f"  waiting... {memo_idx}", flush=True)
        time.sleep(5)
    else:
        print("  search indexes not ready in 5 min — bailing")
        return 2

    step("5. integration smoke test (FIRED vs BLOCKED)")
    rc = run_py("tests/smoke/test_integration.py", timeout=120)
    if rc != 0:
        print("  integration check FAILED")
        return 1

    if args.record_replay:
        step(f"6. record events_replay.json (waiting {args.replay_duration}s)")
        rc = run_py("scripts/replay_server.py", "--record",
                    "--duration", str(args.replay_duration),
                    "--src", WS, timeout=args.replay_duration + 30)
        if rc != 0:
            print("  replay recording failed")

    step("DONE — green")
    n_m = db[MEMORIES].count_documents({})
    n_q = db[QUARANTINE].count_documents({})
    n_l = db[RETRIEVAL_LOG].count_documents({})
    print(f"  memories={n_m} quarantine={n_q} retrieval_log={n_l}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
