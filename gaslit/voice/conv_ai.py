"""ElevenLabs Conversational AI — env wiring for widget + server-side metadata."""

from __future__ import annotations

import os

FORENSIC_AUDITOR_SYSTEM_PROMPT = (
    "You are the GASLIT Forensic Auditor. You have access to quarantine "
    "records and provenance chains. Answer questions about memory poisoning "
    "incidents concisely and professionally."
)


def get_agent_id() -> str | None:
    """Public Conv AI agent id (mirrors NEXT_PUBLIC_ELEVENLABS_AGENT_ID in frontend)."""
    return os.environ.get("ELEVENLABS_AGENT_ID") or os.environ.get(
        "NEXT_PUBLIC_ELEVENLABS_AGENT_ID",
    )


def convai_widget_script_url() -> str:
    """CDN script used by the embedded Conv AI widget (ElevenLabs standard embed)."""
    return "https://unpkg.com/@elevenlabs/convai-widget-embed"


def build_public_config() -> dict:
    """Safe-to-expose config for the Next.js client."""
    aid = get_agent_id()
    return {
        "agent_id": aid,
        "system_prompt_hint": FORENSIC_AUDITOR_SYSTEM_PROMPT[:200] + "…",
    }
