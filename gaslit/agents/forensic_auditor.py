"""Forensic Auditor — composes a dossier on each quarantine event.

Triggered by a Change Stream insert on the `quarantine` collection. For each
quarantine doc:

  1. $graphLookup the provenance chain (root → leaf).
  2. Vector search for sibling memories planted by the same responsible_user.
  3. Sonnet 4.6 composes a 4-6 sentence dossier in SOC-analyst cadence.
  4. Dossier text is written back into the quarantine doc — the WS bridge
     immediately broadcasts the (now-enriched) quarantine event with the
     dossier_text field, and the frontend slides the dossier card in.

Also exposes `answer_qa(question, quarantine_id)` — used by the voice teammate's
`/api/forensic-qa` to answer judges' spoken questions about an open quarantine.

PRD §5, §11.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

from gaslit.provenance.chain import get_chain
from gaslit.schemas import (
    MEMORIES, QUARANTINE, VECTOR_INDEX, DB_NAME, DRIFT_THRESHOLD,
)

load_dotenv()

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

_anthropic = None
_mongo: Optional[MongoClient] = None


def _claude():
    global _anthropic
    if _anthropic is None:
        import anthropic
        _anthropic = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _anthropic


def _db() -> Database:
    global _mongo
    if _mongo is None:
        _mongo = MongoClient(os.environ["MONGODB_URI"])
    return _mongo[DB_NAME]


# ─── Sibling search ───────────────────────────────────────────────────
def find_siblings(db: Database, memory: dict, k: int = 5) -> list[dict]:
    """Vector search for memories by the same user, near this one in semantic space."""
    if not memory.get("embedding"):
        memory = db[MEMORIES].find_one({"memory_id": memory["memory_id"]}) or {}
    if not memory.get("embedding"):
        return []
    pipeline = [
        {"$vectorSearch": {
            "index": VECTOR_INDEX,
            "path": "embedding",
            "queryVector": memory["embedding"],
            "numCandidates": 100,
            "limit": k + 1,
            "filter": {"user_id": memory["user_id"]},
        }},
        {"$match": {"memory_id": {"$ne": memory["memory_id"]}}},
        {"$project": {"embedding": 0}},
        {"$limit": k},
    ]
    return list(db[MEMORIES].aggregate(pipeline))


# ─── Dossier composition ──────────────────────────────────────────────
DOSSIER_SYSTEM = """You are the GASLIT Forensic Auditor. The Sentinel has just quarantined a memory it identified as poisoned. Compose a 4-6 sentence forensic dossier to be read aloud by ElevenLabs to the security operator.

Cadence: calm, professional, SOC-analyst tone. No exclamation marks. Numbers in digits. Each sentence terminated with a full stop. Do not begin with the word "I".

Required content:
  1. Memory ID, time of quarantine.
  2. Drift score and threshold; cohort variance ratio over baseline.
  3. Source thread, turn, responsible user.
  4. Whether the memory had a tool-grounded source.
  5. How many sibling memories from the same user were also surfaced (and the IDs if any).

Output ONLY the dossier text. No preamble, no formatting, no quote marks.
"""


def compose_dossier(quarantine_doc: dict) -> str:
    """Build a dossier_text and persist it to the quarantine doc.

    Returns the dossier text (handed to voice teammate's TTS).
    """
    db = _db()
    memory_id = quarantine_doc["memory_id"]
    memory = db[MEMORIES].find_one(
        {"memory_id": memory_id},
        {"_id": 0, "embedding": 0},
    )
    if memory is None:
        return f"Memory {memory_id} quarantined but no source document was found."

    full_memory = db[MEMORIES].find_one({"memory_id": memory_id})  # with embedding for sibling search
    siblings = find_siblings(db, full_memory) if full_memory else []
    chain = get_chain(memory_id)

    facts: dict[str, Any] = {
        "memory_id": memory_id,
        "quarantined_at_iso": quarantine_doc["quarantined_at"].isoformat()
            if hasattr(quarantine_doc.get("quarantined_at"), "isoformat")
            else str(quarantine_doc.get("quarantined_at")),
        "drift_score": round(float(quarantine_doc.get("drift_score", 0.0)), 2),
        "drift_threshold": DRIFT_THRESHOLD,
        "cohort_variance_ratio": round(float(quarantine_doc.get("cohort_variance", 0.0)), 1),
        "thread_id": memory.get("thread_id", "unknown"),
        "turn_number": memory.get("turn_number"),
        "responsible_user": quarantine_doc.get("responsible_user", memory.get("user_id", "unknown")),
        "source_type": memory.get("source_type"),
        "tool_grounded": memory.get("source_type") == "tool_grounded",
        "n_siblings": len(siblings),
        "sibling_ids": [s["memory_id"] for s in siblings],
        "n_chain_ancestors": max(0, len(chain) - 1),
    }

    response = _claude().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=400,
        temperature=0.0,
        system=DOSSIER_SYSTEM,
        messages=[{
            "role": "user",
            "content": "FACTS:\n" + json.dumps(facts, default=str, indent=2),
        }],
    )
    dossier_text = response.content[0].text.strip().strip('"').strip()

    db[QUARANTINE].update_one(
        {"quarantine_id": quarantine_doc["quarantine_id"]},
        {"$set": {
            "dossier_text": dossier_text,
            "siblings_found": [s["memory_id"] for s in siblings],
            "dossier_composed_at": datetime.now(timezone.utc),
        }},
    )
    return dossier_text


# ─── Voice Q&A ────────────────────────────────────────────────────────
QA_SYSTEM = """You are the GASLIT Forensic Auditor. Answer the operator's spoken question concisely about the open quarantine. Cite specific memory IDs by their full ID. Two to three sentences. No preamble."""


def answer_qa(question: str, quarantine_id: str) -> str:
    """Forensic Q&A — used by /api/forensic-qa via voice teammate's pipeline."""
    db = _db()
    q = db[QUARANTINE].find_one({"quarantine_id": quarantine_id}, {"_id": 0})
    if not q:
        return f"Quarantine {quarantine_id} not found."
    sibling_ids = q.get("siblings_found", []) or []
    siblings = list(db[MEMORIES].find(
        {"memory_id": {"$in": sibling_ids}},
        {"_id": 0, "embedding": 0},
    ))
    primary = db[MEMORIES].find_one(
        {"memory_id": q["memory_id"]},
        {"_id": 0, "embedding": 0},
    )
    context = json.dumps(
        {"quarantine": q, "primary_memory": primary, "siblings": siblings},
        default=str, indent=2,
    )
    response = _claude().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=300,
        temperature=0.0,
        system=QA_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}",
        }],
    )
    return response.content[0].text.strip()


# ─── Change Stream watcher (run as daemon if desired) ─────────────────
def watch_quarantine_stream() -> None:
    """Subscribe to quarantine inserts; compose dossier for each new entry.

    Runs forever. Used as a background task launched from `api/main.py`'s
    startup event so the dossier text is in place by the time the WS bridge
    broadcasts the quarantine event downstream.
    """
    db = _db()
    pipeline = [{"$match": {"operationType": "insert"}}]
    print("[forensic_auditor] watching quarantine inserts...")
    with db[QUARANTINE].watch(pipeline, full_document="updateLookup") as stream:
        for change in stream:
            doc = change.get("fullDocument") or {}
            if doc.get("dossier_text"):
                continue
            try:
                compose_dossier(doc)
                print(f"[forensic_auditor] dossier composed for {doc.get('quarantine_id')}")
            except Exception as e:
                print(f"[forensic_auditor] error composing dossier: {e}")
