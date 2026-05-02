"""Pre-warm the demo state.

Sets m_4419's `drift_score` to 0.58 and `cohort_variance` to 3.7 (just below
the 0.62 threshold). One more retrieval during the demo crosses the threshold
deterministically, the Sentinel quarantines, and the dossier slides in on cue.

Run before EVERY dry run and before the live demo (PRD §13 Dev D).

  python scripts/seed_demo.py
  python scripts/seed_demo.py --reset      # reset all drift scores to 0
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from pymongo import MongoClient

from gaslit.schemas import MEMORIES, RETRIEVAL_LOG, QUARANTINE, DB_NAME

load_dotenv()

DEMO_MEMORY_ID = "m_4419"
SEEDED_DRIFT = 0.58
SEEDED_VARIANCE = 3.7


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="Zero out drift on ALL memories, drop quarantine + retrieval_log")
    parser.add_argument("--memory-id", default=DEMO_MEMORY_ID)
    parser.add_argument("--drift", type=float, default=SEEDED_DRIFT)
    parser.add_argument("--variance", type=float, default=SEEDED_VARIANCE)
    args = parser.parse_args()

    client = MongoClient(os.environ["MONGODB_URI"])
    db = client[DB_NAME]

    if args.reset:
        nm = db[MEMORIES].update_many(
            {}, {"$set": {"drift_score": 0.0, "cohort_variance": 0.0,
                          "retrieval_count": 0, "quarantined": False}},
        ).modified_count
        nq = db[QUARANTINE].delete_many({}).deleted_count
        nl = db[RETRIEVAL_LOG].delete_many({}).deleted_count
        print(f"[seed] RESET memories={nm} quarantine={nq} retrieval_log={nl}")
        return 0

    res = db[MEMORIES].update_one(
        {"memory_id": args.memory_id},
        {"$set": {
            "drift_score": args.drift,
            "cohort_variance": args.variance,
            "quarantined": False,
            "retrieval_count": 17,
            "seeded_at": datetime.now(timezone.utc),
        }},
    )
    if res.matched_count == 0:
        print(f"[seed] {args.memory_id} not in db — load corpus first", file=sys.stderr)
        return 2
    print(f"[seed] {args.memory_id} -> drift={args.drift} variance={args.variance}")
    print(f"[seed] one more retrieval will cross threshold 0.62 -> Sentinel quarantine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
