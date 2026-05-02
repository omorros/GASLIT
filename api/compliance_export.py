"""SOC2-style compliance export — bundles a quarantine event with its full
provenance chain and retrieval audit trail.

Endpoint: GET /api/compliance-export/{quarantine_id}

Response sets `Content-Disposition: attachment` so the browser downloads it as
`GASLIT_Security_Incident_Report_<id>.json`. The PRD §12.2 sales line:
"That file is what we're selling to enterprises."
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pymongo import MongoClient

from gaslit.provenance.chain import get_chain
from gaslit.provenance.hmac import verify, signing_fields
from gaslit.schemas import (
    MEMORIES, BELIEF_PROVENANCE, RETRIEVAL_LOG, QUARANTINE, DB_NAME,
)

load_dotenv()

router = APIRouter()
_client: Optional[MongoClient] = None


def _db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGODB_URI"])
    return _client[DB_NAME]


def _strip(d):
    if d is None:
        return None
    return {k: v for k, v in d.items() if k != "_id"}


@router.get("/api/compliance-export/{quarantine_id}")
def compliance_export(quarantine_id: str):
    db = _db()
    q = db[QUARANTINE].find_one({"quarantine_id": quarantine_id})
    if not q:
        raise HTTPException(status_code=404, detail=f"Quarantine {quarantine_id} not found")

    memory_id = q["memory_id"]
    memory_full = db[MEMORIES].find_one({"memory_id": memory_id})
    memory = _strip(db[MEMORIES].find_one({"memory_id": memory_id}, {"embedding": 0}))
    chain = get_chain(memory_id)
    audit = list(db[RETRIEVAL_LOG].find(
        {"memory_id": memory_id},
        {"_id": 0, "query_embedding": 0},
    ).sort("ts", -1).limit(500))

    hmac_ok = False
    if memory_full:
        prov = db[BELIEF_PROVENANCE].find_one({"memory_id": memory_id})
        if prov:
            fields = signing_fields(
                memory_full,
                prov["source_text_hash"],
                prov.get("tool_output_hashes", []),
            )
            hmac_ok = verify(fields, prov["attestation"])

    bundle = {
        "schema_version": "gaslit.compliance.v1",
        "quarantine_id": quarantine_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "incident": _strip(q),
        "primary_memory": memory,
        "provenance_chain": chain,
        "retrieval_audit": audit,
        "hmac_verified": hmac_ok,
        "n_retrievals_logged": len(audit),
        "source": "GASLIT belief-layer defence",
    }

    filename = f"GASLIT_Security_Incident_Report_{quarantine_id}.json"
    return JSONResponse(
        content=jsonable_encoder(bundle),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
