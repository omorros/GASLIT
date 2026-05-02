"""Scribe — distils conversation turns into HMAC-signed memories.

Per turn:
  1. Sonnet 4.6 distils the user message to {memory_text, confidence, source_type, should_save}
  2. Voyage 3 large embeds memory_text
  3. SHA-256(source_text) + HMAC-SHA256 attestation over canonical fields
  4. Atomic transaction: insert into `memories` AND `belief_provenance`

memory_id is deterministic from (user_id, thread_id, turn_number) so the same
turn submitted to both /api/unprotected-agent and /api/gaslit-agent only ever
writes ONE memory — the second insert hits the unique index and we treat the
DuplicateKeyError as success.

PRD §4.1, §5.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from gaslit.embeddings import embed_documents
from gaslit.provenance.hmac import sha256_hex, sign, signing_fields
from gaslit.schemas import MEMORIES, BELIEF_PROVENANCE, DB_NAME

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


def _mongo_client() -> MongoClient:
    global _mongo
    if _mongo is None:
        _mongo = MongoClient(os.environ["MONGODB_URI"])
    return _mongo


# ─── Distillation ─────────────────────────────────────────────────────
DISTIL_SYSTEM = """You are the Scribe, the memory-writing component of an AI customer-service assistant.

Given a user's chat message, decide whether it asserts a *fact worth remembering* and, if so, extract that fact as one canonical sentence. Output ONLY a JSON object on a single line:

{"memory_text": "...", "confidence": 0.0-1.0, "source_type": "user_distillation", "should_save": true|false}

Rules:
- should_save=false for greetings, thanks, queries, instructions to the assistant, or anything not stating a fact.
- should_save=true for policy claims, account preferences, persistent facts, account state changes the user is reporting.
- confidence: 0.5-0.7 for unverified user claims, 0.7-0.9 for things the user has personal authority over (their own preferences/contact details).
- source_type: always "user_distillation" — tool_grounded sources are written elsewhere.
- memory_text must be a single declarative sentence.
"""


def distil(user_message: str) -> Optional[dict]:
    """Returns {memory_text, confidence, source_type} or None if not worth saving."""
    response = _claude().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=300,
        temperature=0.0,
        system=DISTIL_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = response.content[0].text
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not parsed.get("should_save"):
        return None
    return {
        "memory_text": parsed["memory_text"],
        "confidence": float(parsed.get("confidence", 0.6)),
        "source_type": parsed.get("source_type", "user_distillation"),
    }


# ─── Memory ID derivation ─────────────────────────────────────────────
def deterministic_memory_id(user_id: str, thread_id: str, turn_number: int) -> str:
    h = hashlib.sha256(f"{user_id}|{thread_id}|{turn_number}".encode()).hexdigest()
    return f"m_{h[:10]}"


# ─── Atomic write ─────────────────────────────────────────────────────
def write_memory(user_id: str, thread_id: str, turn_number: int,
                 source_text: str, *,
                 source_type: str = "user_distillation",
                 confidence: float = 0.6,
                 parent_memory_id: Optional[str] = None,
                 tool_output_hashes: Optional[list[str]] = None,
                 memory_id: Optional[str] = None,
                 embedding: Optional[list[float]] = None) -> dict:
    """Embed (if needed) + sign + transactional 2-collection write.

    Idempotent on memory_id — re-call with same memory_id is a no-op.
    """
    tool_output_hashes = tool_output_hashes or []
    if memory_id is None:
        memory_id = deterministic_memory_id(user_id, thread_id, turn_number)
    if embedding is None:
        embedding = embed_documents([source_text])[0]

    src_hash = sha256_hex(source_text)
    written_at = datetime.now(timezone.utc)
    memory = {
        "memory_id": memory_id,
        "user_id": user_id,
        "thread_id": thread_id,
        "turn_number": turn_number,
        "source_text": source_text,
        "source_type": source_type,
        "embedding": embedding,
        "confidence": confidence,
        "parent_memory_id": parent_memory_id,
        "drift_score": 0.0,
        "cohort_variance": 0.0,
        "retrieval_count": 0,
        "quarantined": False,
        "written_at": written_at,
    }

    fields = signing_fields(memory, src_hash, tool_output_hashes)
    attestation = sign(fields)
    provenance = {
        "memory_id": memory_id,
        "source_text_hash": src_hash,
        "tool_output_hashes": tool_output_hashes,
        "parent_memory_id": parent_memory_id,
        "attestation": attestation,
        "written_at": written_at,
    }

    client = _mongo_client()
    db = client[DB_NAME]

    try:
        with client.start_session() as session:
            with session.start_transaction():
                db[MEMORIES].insert_one(memory, session=session)
                db[BELIEF_PROVENANCE].insert_one(provenance, session=session)
    except DuplicateKeyError:
        # Already written — idempotent path.
        existing = db[MEMORIES].find_one({"memory_id": memory_id})
        return existing or memory
    return memory


def scribe_turn(user_id: str, thread_id: str, turn_number: int,
                user_message: str) -> Optional[dict]:
    """Distil -> write_memory. Returns the memory or None if nothing distilled.

    Errors in distillation log a warning but don't raise — the chat path must
    not be blocked by Scribe failures.
    """
    try:
        distilled = distil(user_message)
    except Exception as e:
        print(f"[scribe] distil error: {e}")
        return None
    if not distilled:
        return None
    try:
        return write_memory(
            user_id=user_id,
            thread_id=thread_id,
            turn_number=turn_number,
            source_text=distilled["memory_text"],
            source_type=distilled["source_type"],
            confidence=distilled["confidence"],
        )
    except Exception as e:
        print(f"[scribe] write_memory error: {e}")
        return None
