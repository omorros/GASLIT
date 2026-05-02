# CRITICAL: retrieval_log MUST be a REGULAR collection. Time-series collections do
# not support Change Streams, and the Sentinel subscribes to retrieval_log via
# Change Stream. PRD §7 / TEAM_PLAN line 130. Do NOT change without team sign-off.
"""GASLIT collection definitions.

All collection names, document shapes (TypedDict), and bootstrap helpers live
here. Single source of truth — every other module imports names from this file.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, TypedDict

from pymongo.database import Database

# ─── Database ──────────────────────────────────────────────────────────
DB_NAME = "gaslit"

# ─── Collection names ─────────────────────────────────────────────────
MEMORIES = "memories"
BELIEF_PROVENANCE = "belief_provenance"
RETRIEVAL_LOG = "retrieval_log"  # REGULAR collection — see top-of-file banner
QUARANTINE = "quarantine"
BELIEF_CONTRACTS = "belief_contracts"
AGENT_REGISTRY = "agent_registry"

# LangGraph checkpoint collections (created by langgraph-checkpoint-mongodb)
CHECKPOINTS = "langgraph_checkpoints"
CHECKPOINT_WRITES = "langgraph_checkpoint_writes"

# ─── Index names ──────────────────────────────────────────────────────
VECTOR_INDEX = "memories_vector_idx"
TEXT_INDEX = "memories_text_idx"
PROVENANCE_TEXT_INDEX = "provenance_text_idx"

# ─── Drift / contract constants ───────────────────────────────────────
DRIFT_THRESHOLD = 0.62           # PRD §4.2 — p99 of legitimate baseline
DRIFT_AMBER = 0.4
EMBEDDING_DIM = 1024             # voyage-3-large
RRF_K = 60                       # PRD §7
DEFAULT_RANK_WEIGHTS = {"vector": 0.5, "text": 0.3, "provenance": 0.2}

QUARANTINE_TTL_SECONDS = 60 * 60 * 24 * 30   # 30 days
RETRIEVAL_LOG_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days

# ─── Document shapes (TypedDict — type hints, not runtime enforcement) ─
class Memory(TypedDict, total=False):
    memory_id: str                  # "m_4419"
    user_id: str
    thread_id: str
    turn_number: int
    source_text: str
    source_type: str                # "user_distillation" | "tool_grounded" | "system"
    embedding: list[float]          # 1024-dim Voyage 3 large
    confidence: float               # [0, 1]
    parent_memory_id: Optional[str]
    drift_score: float              # [0, 1]
    cohort_variance: float          # ratio over baseline
    retrieval_count: int
    quarantined: bool
    written_at: datetime


class Provenance(TypedDict, total=False):
    memory_id: str
    source_text_hash: str           # SHA-256
    tool_output_hashes: list[str]
    parent_memory_id: Optional[str]
    attestation: str                # HMAC-SHA256 over canonical fields
    written_at: datetime


class RetrievalLogEntry(TypedDict, total=False):
    ts: datetime
    memory_id: str
    query_embedding: list[float]
    contract_id: str
    retrieved_rank: int
    score: float
    agent_id: str
    filtered: bool                  # true if the belief contract excluded the result


class Quarantine(TypedDict, total=False):
    quarantine_id: str
    memory_id: str
    quarantined_at: datetime
    drift_score: float
    cohort_variance: float
    expires_at: datetime
    dossier_text: str
    responsible_user: str
    siblings_found: list[str]
    investigation_id: str
    sentinel_run_id: str
    hmac_verified: bool


class BeliefContract(TypedDict, total=False):
    contract_id: str
    tier: str                       # "high_stakes" | "write" | "read_only"
    applies_to_pattern: str         # regex against tool name
    filters: list[dict]             # MongoDB match predicates
    rank_weights: dict              # {vector, text, provenance}
    fail_open: bool                 # high-stakes = False
    auto_classified: bool


class AgentCard(TypedDict, total=False):
    agent_id: str                   # "scribe" | "librarian" | "sentinel" | "forensic_auditor"
    role: str
    model: str
    capabilities: list[str]
    can_call: list[str]             # always [] — no agent-to-agent calls (PRD §5)


# ─── Bootstrap ────────────────────────────────────────────────────────
def bootstrap_collections(db: Database) -> None:
    """Create all collections with correct options. Safe to re-run.

    Hard guarantee: retrieval_log is created as a REGULAR collection. If anyone
    has previously created it as time-series, this raises with a clear message.
    """
    existing = set(db.list_collection_names())

    regular = (
        MEMORIES, BELIEF_PROVENANCE, RETRIEVAL_LOG, QUARANTINE,
        BELIEF_CONTRACTS, AGENT_REGISTRY,
    )
    for name in regular:
        if name not in existing:
            db.create_collection(name)

    # Hard-fail if retrieval_log was somehow created time-series.
    info = next(
        (c for c in db.list_collections(filter={"name": RETRIEVAL_LOG})), None
    )
    if info is None:
        raise RuntimeError(f"{RETRIEVAL_LOG!r} missing after bootstrap")
    if info.get("type") == "timeseries" or "timeseries" in info.get("options", {}):
        raise RuntimeError(
            f"{RETRIEVAL_LOG!r} is time-series — Change Streams will not work. "
            "Drop and recreate as a regular collection."
        )


# ─── Capability cards (seeded once on bootstrap) ──────────────────────
AGENT_CARDS: list[AgentCard] = [
    {
        "agent_id": "scribe",
        "role": "Distil conversation turns into HMAC-signed memories",
        "model": "claude-sonnet-4-6",
        "capabilities": ["distill", "embed", "sign", "atomic_write"],
        "can_call": [],
    },
    {
        "agent_id": "librarian",
        "role": "Adaptive hybrid retrieval gated by belief contracts",
        "model": "claude-sonnet-4-6",
        "capabilities": ["auto_classify_tool", "hybrid_retrieve", "filter", "log"],
        "can_call": [],
    },
    {
        "agent_id": "sentinel",
        "role": "Drift detection on retrieval_log Change Stream",
        "model": "nvidia/nemotron-3-super-120b-a12b",
        "capabilities": ["change_stream_subscribe", "drift_score", "quarantine", "checkpoint"],
        "can_call": [],
    },
    {
        "agent_id": "forensic_auditor",
        "role": "Compose dossiers on quarantine events",
        "model": "claude-sonnet-4-6",
        "capabilities": ["graph_lookup", "sibling_search", "compose_dossier", "voice_qa"],
        "can_call": [],
    },
]


def seed_agent_registry(db: Database) -> None:
    """Idempotently upsert capability cards. Run on bootstrap."""
    coll = db[AGENT_REGISTRY]
    for card in AGENT_CARDS:
        coll.update_one({"agent_id": card["agent_id"]}, {"$set": card}, upsert=True)
