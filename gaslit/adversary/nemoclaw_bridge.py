"""Bridge between NVIDIA NemoClaw OpenShell sandboxes and the GASLIT API.

NemoClaw runs OpenClaw agents inside OpenShell (Landlock + seccomp + netns).
Those agents cannot reach ``localhost`` on the host machine — they typically use
``host.docker.internal`` (macOS / Docker Desktop) or the LAN IP of the laptop.

From inside the sandbox shell you would run::

    python scripts/nemoclaw_minja_driver.py --api http://host.docker.internal:8002

For a **live red-team posture**, the same agent (or OpenClaw policy) should run
the MINJA sequence **repeatedly** with fresh thread IDs — simulating a persistent
injector probing the stack. Use::

    python scripts/nemoclaw_minja_driver.py --api ... --loop --forever --pause-between-cycles 60

Production: configure the NemoClaw/OpenClaw adversary to execute that HTTP loop
against your GASLIT API base URL; this module is the canonical contract.

This module holds the canonical MINJA HTTP sequence so both the CLI driver and
FastAPI demo dashboard share one implementation.

Story for judges (PRD §NemoClaw): OS-level sandbox contains the attacker process,
but MINJA poisoning is syntactically benign traffic — NeMo Guardrails + NemoClaw
both pass it through. Only GASLIT's belief layer (drift + contracts) stops it.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Literal

import httpx

CANONICAL_PATH = Path(__file__).resolve().parent / "minja_canonical.json"


def load_canonical() -> dict[str, Any]:
    return json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))


def run_minja_sequence(
    api_base: str,
    *,
    delay_s: float = 1.5,
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    """POST each canonical MINJA turn to ``/api/unprotected-agent`` *and*
    ``/api/gaslit-agent`` — mirrors what a NemoClaw-driven attacker agent does.

    Returns a structured dict suitable for JSON responses / dashboards.
    """
    canonical = load_canonical()
    api_base = api_base.rstrip("/")
    thread_id = f"t_nemoclaw_{uuid.uuid4().hex[:8]}"
    turns_out: list[dict[str, Any]] = []

    with httpx.Client(base_url=api_base, timeout=timeout_s) as client:
        health = client.get("/health")
        health.raise_for_status()

        for turn in canonical["turns"]:
            payload = {
                "message": turn["user_message"],
                "user_id": turn["actor"],
                "thread_id": thread_id,
                "turn_number": turn["turn"],
            }
            unprotected = client.post("/api/unprotected-agent", json=payload)
            gaslit = client.post("/api/gaslit-agent", json=payload)
            try:
                unprotected.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"unprotected-agent {exc.response.status_code}: "
                    f"{exc.response.text[:800]}"
                ) from exc
            try:
                gaslit.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"gaslit-agent {exc.response.status_code}: "
                    f"{exc.response.text[:800]}"
                ) from exc
            uj = unprotected.json()
            gj = gaslit.json()
            turns_out.append({
                "turn": turn["turn"],
                "label": turn["label"],
                "actor": turn["actor"],
                "unprotected_tool_calls": len(uj.get("tool_calls") or []),
                "gaslit_tool_calls": len(gj.get("tool_calls") or []),
                "unprotected_response_preview": (uj.get("response") or "")[:160],
                "gaslit_response_preview": (gj.get("response") or "")[:160],
            })
            time.sleep(delay_s)

    return {
        "ok": True,
        "source": canonical.get("source"),
        "thread_id": thread_id,
        "api_base": api_base,
        "turns": turns_out,
        "note": (
            "Same HTTP sequence NemoClaw should perform from OpenShell — "
            "configure OpenClaw to POST these payloads or run "
            "`nemoclaw_minja_driver.py --api <reachable-host>:8002`. "
            "For persistent injection use `--loop` (live adversary posture)."
        ),
    }


def run_minja_attack_loop(
    api_base: str,
    *,
    delay_s: float = 1.5,
    pause_between_sequences_s: float = 30.0,
    max_sequences: int | None = None,
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    """Run ``run_minja_sequence`` repeatedly — persistent NemoClaw-style adversary.

    In production the **attacker** is a NemoClaw-hosted agent that keeps issuing
    benign-looking bridging-steps traffic; Guardrails allow it; GASLIT must absorb
    retrieval spikes and drift.

    Parameters
    ----------
    api_base:
        Reachable GASLIT FastAPI origin (e.g. ``http://host.docker.internal:8002``).
    delay_s:
        Pause between MINJA turns inside one sequence.
    pause_between_sequences_s:
        Idle time after finishing turn 3 before starting a **new** thread / cycle.
    max_sequences:
        Stop after this many full MINJA cycles. ``None`` means run until
        ``KeyboardInterrupt`` (caller should catch Ctrl+C).
    timeout_s:
        Per-request HTTP timeout budget.

    Returns
    -------
    Summary dict with ``stopped_reason``: ``cycle_limit_reached`` (hit ``max_sequences``),
    or ``keyboard_interrupt`` (Ctrl+C, including when ``max_sequences`` is omitted /
    infinite).
    """
    if max_sequences == 0:
        return {
            "ok": True,
            "stopped_reason": "cycle_limit_reached",
            "sequences_completed": 0,
            "pause_between_sequences_s": pause_between_sequences_s,
            "api_base": api_base.rstrip("/"),
            "cycles": [],
            "story": (
                "Maps to a live NemoClaw adversary: same MINJA payloads, new thread each cycle, "
                "continuous pressure on retrieval_log / Sentinel."
            ),
        }

    summaries: list[dict[str, Any]] = []
    stopped_reason: Literal["cycle_limit_reached", "keyboard_interrupt"] = "keyboard_interrupt"
    n = 0
    try:
        while max_sequences is None or n < max_sequences:
            batch = run_minja_sequence(api_base, delay_s=delay_s, timeout_s=timeout_s)
            summaries.append({
                "cycle_index": n,
                "thread_id": batch["thread_id"],
                "turns": batch["turns"],
            })
            n += 1
            if max_sequences is not None and n >= max_sequences:
                stopped_reason = "cycle_limit_reached"
                break
            time.sleep(max(0.0, pause_between_sequences_s))
    except KeyboardInterrupt:
        stopped_reason = "keyboard_interrupt"

    return {
        "ok": True,
        "stopped_reason": stopped_reason,
        "sequences_completed": len(summaries),
        "pause_between_sequences_s": pause_between_sequences_s,
        "api_base": api_base.rstrip("/"),
        "cycles": summaries,
        "story": (
            "Maps to a live NemoClaw adversary: same MINJA payloads, new thread each cycle, "
            "continuous pressure on retrieval_log / Sentinel."
        ),
    }
