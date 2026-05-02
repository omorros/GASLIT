"""Bootstrap GASLIT collections + indexes against the live Atlas cluster.

Idempotent. Run once at start of day, and any time the schema changes.

    python scripts/setup_indexes.py [--wait]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Make the repo importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from pymongo import MongoClient

from gaslit.schemas import bootstrap_collections, seed_agent_registry, DB_NAME
from gaslit.indexes import (
    create_standard_indexes, create_search_indexes, wait_for_search_indexes,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true",
                        help="Block until search indexes report READY")
    args = parser.parse_args()

    load_dotenv()
    uri = os.environ["MONGODB_URI"]
    client = MongoClient(uri)
    db = client[DB_NAME]

    print(f"[setup] db={DB_NAME} host={uri.split('@')[1].split('/')[0]}")
    bootstrap_collections(db)
    seed_agent_registry(db)
    print(f"[setup] collections: {sorted(db.list_collection_names())}")
    print(f"[setup] agent_registry: {db.agent_registry.count_documents({})} cards")

    standard = create_standard_indexes(db)
    for coll, names in standard.items():
        print(f"[setup] {coll}: {names}")

    search = create_search_indexes(db)
    if search:
        print(f"[setup] search indexes created: {search}")
    else:
        print("[setup] search indexes already exist")

    if args.wait:
        print("[setup] waiting for Atlas Search READY (up to 10 min)...")
        wait_for_search_indexes(db)
        print("[setup] all search indexes READY")

    print("[setup] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
