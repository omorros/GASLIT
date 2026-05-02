#!/usr/bin/env python3
"""
Create the GASLIT Forensic Auditor on ElevenLabs Conversational AI (Conv AI).

Requires: ELEVENLABS_API_KEY in the environment (or a .env file next to this repo).

Usage:
  export ELEVENLABS_API_KEY=sk_...
  python scripts/create_convai_agent.py
  python scripts/create_convai_agent.py --write-env
  (writes agent id into .env + frontend/.env.local)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "frontend" / ".env.local")


def _upsert_env(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    new_lines: list[str] = []
    handled: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            handled.add(key)
        else:
            new_lines.append(line)
    for key, val in updates.items():
        if key not in handled:
            new_lines.append(f"{key}={val}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create ElevenLabs Conv AI agent for GASLIT")
    parser.add_argument(
        "--write-env",
        action="store_true",
        help=(
            "Write ELEVENLABS_AGENT_ID and NEXT_PUBLIC_ELEVENLABS_AGENT_ID "
            "to .env and frontend/.env.local"
        ),
    )
    args = parser.parse_args()

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print(
            "Missing ELEVENLABS_API_KEY. Create a key at "
            "https://elevenlabs.io/app/settings/api-keys",
            file=sys.stderr,
        )
        sys.exit(1)

    from elevenlabs import ConversationalConfig, ElevenLabs
    from elevenlabs.types.agent_config import AgentConfig
    from elevenlabs.types.prompt_agent_api_model_output import PromptAgentApiModelOutput
    from elevenlabs.types.tts_conversational_config_output import TtsConversationalConfigOutput

    from gaslit.voice.conv_ai import FORENSIC_AUDITOR_SYSTEM_PROMPT

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
    # Conv AI English agents require turbo or flash **v2** (not v2.5) per API validation.
    tts_model = os.environ.get("ELEVENLABS_CONVAI_TTS_MODEL", "eleven_flash_v2")
    llm = os.environ.get("ELEVENLABS_CONVAI_LLM", "claude-sonnet-4-6")

    client = ElevenLabs(api_key=api_key)

    conversation_config = ConversationalConfig(
        tts=TtsConversationalConfigOutput(
            model_id=tts_model,  # type: ignore[arg-type]
            voice_id=voice_id,
        ),
        agent=AgentConfig(
            first_message=(
                "I'm the GASLIT Forensic Auditor — I explain quarantined memories, drift "
                "against threshold, provenance, and sibling attacks. What would you like to know?"
            ),
            language="en",
            prompt=PromptAgentApiModelOutput(
                prompt=FORENSIC_AUDITOR_SYSTEM_PROMPT,
                llm=llm,  # type: ignore[arg-type]
                temperature=0.3,
            ),
        ),
    )

    resp = client.conversational_ai.agents.create(
        name="GASLIT Forensic Auditor",
        tags=["gaslit", "forensic-auditor"],
        conversation_config=conversation_config,
    )
    agent_id = resp.agent_id
    print("Created Conv AI agent.")
    print(f"  agent_id: {agent_id}")
    print("Add to your frontend (public): NEXT_PUBLIC_ELEVENLABS_AGENT_ID=" + agent_id)
    print("Add to backend (optional): ELEVENLABS_AGENT_ID=" + agent_id)

    if args.write_env:
        env_root = ROOT / ".env"
        env_fe = ROOT / "frontend" / ".env.local"
        updates = {
            "ELEVENLABS_AGENT_ID": agent_id,
            "NEXT_PUBLIC_ELEVENLABS_AGENT_ID": agent_id,
        }
        _upsert_env(env_root, updates)
        _upsert_env(env_fe, updates)
        print(f"Updated {env_root} and {env_fe}")


if __name__ == "__main__":
    main()
