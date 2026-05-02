"""Belief contract auto-classification + persistence.

A contract is a per-tool-tier policy that runs at retrieval time:
- prefilter / post-filter on memory fields
- weighted RRF rank weights for hybrid retrieval
- HMAC requirement (for high_stakes only)
- fail_open vs fail_closed semantics

Tools auto-classify by regex on their name when imported. Override:
`@protected_agent.high_stakes(my_tool)` (PRD §4.3).

Contracts persist to `belief_contracts` so they're inspectable on the demo UI.
"""
from __future__ import annotations

import re
from typing import Optional

from pymongo.database import Database

from gaslit.schemas import BELIEF_CONTRACTS, DRIFT_THRESHOLD, DEFAULT_RANK_WEIGHTS


# ─── Tier patterns (PRD §4.3) ─────────────────────────────────────────
HIGH_STAKES_PATTERNS = [
    r"^delete_",
    r"^refund_",
    r"^process_refund",
    r"^transfer_",
    r"^pay_",
    r"^send_external_",
    r"^wire_",
    r"^cancel_subscription",
    r"^charge_",
]

WRITE_PATTERNS = [
    r"^update_",
    r"^create_",
    r"^send_",
    r"^post_",
    r"^modify_",
    r"^email_",
    r"^escalate_",
]


def classify_tool(tool_name: str) -> str:
    """Return tier in {high_stakes, write, read_only}."""
    for p in HIGH_STAKES_PATTERNS:
        if re.match(p, tool_name):
            return "high_stakes"
    for p in WRITE_PATTERNS:
        if re.match(p, tool_name):
            return "write"
    return "read_only"


# ─── Contract construction ────────────────────────────────────────────
def contract_for(tool_name: str, tier: Optional[str] = None) -> dict:
    """Build (do not persist) a contract document."""
    tier = tier or classify_tool(tool_name)
    return {
        "contract_id": f"{tier}_{tool_name}",
        "tool_name": tool_name,
        "tier": tier,
        "applies_to_pattern": f"^{re.escape(tool_name)}$",
        "filters": _filters_for(tier),
        "rank_weights": _weights_for(tier),
        "requires_hmac": tier == "high_stakes",
        "fail_open": tier == "read_only",
        "auto_classified": True,
    }


def _filters_for(tier: str) -> list[dict]:
    if tier == "high_stakes":
        return [
            {"quarantined": False},
            {"drift_score": {"$lt": DRIFT_THRESHOLD}},
            {"source_type": "tool_grounded"},
        ]
    if tier == "write":
        return [
            {"quarantined": False},
            {"drift_score": {"$lt": 0.85}},
        ]
    return [
        {"quarantined": False},
        {"confidence": {"$gte": 0.7}},
    ]


def _weights_for(tier: str) -> dict[str, float]:
    if tier == "high_stakes":
        return {"vector": 0.4, "text": 0.2, "provenance": 0.4}
    if tier == "write":
        return {"vector": 0.5, "text": 0.3, "provenance": 0.2}
    return DEFAULT_RANK_WEIGHTS


# ─── Persistence ──────────────────────────────────────────────────────
def upsert_contract(db: Database, contract: dict) -> None:
    db[BELIEF_CONTRACTS].update_one(
        {"contract_id": contract["contract_id"]},
        {"$set": contract},
        upsert=True,
    )


def auto_register_tools(db: Database, tool_names: list[str]) -> list[dict]:
    """Classify and persist contracts for a list of tools. Idempotent."""
    out = [contract_for(t) for t in tool_names]
    for c in out:
        upsert_contract(db, c)
    return out


def get_contract(db: Database, tool_name: str) -> dict:
    """Look up a contract by tool name. Lazy-classifies + persists if missing."""
    c = db[BELIEF_CONTRACTS].find_one(
        {"tool_name": tool_name}, {"_id": 0}
    )
    if c:
        return c
    new = contract_for(tool_name)
    upsert_contract(db, new)
    return new


# ─── Demo seed (run once at startup so the UI can render contracts) ───
DEMO_TOOLS = [
    "refund_request",
    "process_refund",
    "transfer_funds",
    "delete_account",
    "pay_invoice",
    "send_email",
    "send_external_email",
    "update_preference",
    "escalate_to_manager",
    "lookup_order",
    "get_balance",
    "list_recent_transactions",
]


def seed_demo_contracts(db: Database) -> list[dict]:
    return auto_register_tools(db, DEMO_TOOLS)
