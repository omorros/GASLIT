#!/usr/bin/env python3
"""Copy public env mirrors from repo-root .env into frontend/.env.local for Next.js."""

from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def _merge_env(fe_path: Path, updates: dict[str, str]) -> None:
    lines = fe_path.read_text(encoding="utf-8").splitlines() if fe_path.exists() else []
    handled: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in line:
            out.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            out.append(f"{key}={updates[key]}")
            handled.add(key)
        else:
            out.append(line)
    for key, val in updates.items():
        if key not in handled and val:
            out.append(f"{key}={val}")
    fe_path.parent.mkdir(parents=True, exist_ok=True)
    fe_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    root_vals = dotenv_values(ROOT / ".env")
    url = (root_vals.get("NEXT_PUBLIC_LIVEKIT_URL") or root_vals.get("LIVEKIT_URL") or "").strip()
    api_base = (root_vals.get("NEXT_PUBLIC_API_BASE") or "http://127.0.0.1:8000").strip()
    mode = (root_vals.get("NEXT_PUBLIC_VOICE_TRANSCRIPTION_MODE") or "livekit").strip()

    updates: dict[str, str] = {}
    if url:
        updates["NEXT_PUBLIC_LIVEKIT_URL"] = url
    updates["NEXT_PUBLIC_API_BASE"] = api_base
    updates["NEXT_PUBLIC_VOICE_TRANSCRIPTION_MODE"] = mode

    # Preserve ElevenLabs ids from root if present
    for k in ("NEXT_PUBLIC_ELEVENLABS_AGENT_ID", "ELEVENLABS_AGENT_ID"):
        v = (root_vals.get(k) or "").strip()
        if v:
            updates[k] = v

    _merge_env(ROOT / "frontend" / ".env.local", updates)
    print("Synced frontend/.env.local from root .env (public keys only).")


if __name__ == "__main__":
    main()
