# GASLIT — Secret Handling

## TL;DR

All secrets live in `.env` (gitignored). Nothing else. No keys in code, no keys in commits, no keys in chat once we're set up. After the hackathon, rotate everything.

## Files

| File | Committed? | Purpose |
|---|---|---|
| `.env` | **NO** (gitignored) | All real keys for local dev. Single source of truth at runtime. |
| `.env.example` | yes | Template — same keys, no values. Safe to share. |
| `docs/secrets.md` | yes | This doc — handling policy. No values. |

## What's in `.env`

Loaded at process start by `python-dotenv` (`load_dotenv()` in every entry-point: `api/main.py`, `ws/bridge.py`, scripts in `scripts/`). Code reads via `os.environ[...]`.

| Key | Owner | Source | Status today |
|---|---|---|---|
| `MONGODB_URI` | Oriol | Atlas → Connect → Drivers → Python | ✅ |
| `MONGODB_DB` | Oriol | static `gaslit` | ✅ |
| `ANTHROPIC_API_KEY` | Oriol | console.anthropic.com → API Keys | ✅ |
| `VOYAGE_API_KEY` | Oriol | dash.voyageai.com → API Keys | ⏳ |
| `FIREWORKS_API_KEY` | Oriol | app.fireworks.ai → API Keys | ⏳ |
| `LANGSMITH_API_KEY` | Oriol | smith.langchain.com → Settings → API Keys | ⏳ |
| `LANGSMITH_PROJECT_URL` | Oriol | LangSmith project page | ⏳ |
| `HMAC_SECRET` | Oriol | `python -c "import secrets; print(secrets.token_hex(32))"` | ✅ |
| `NVIDIA_API_KEY` | Teammate 1 | build.nvidia.com → API key | ⏳ |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Teammate 1 | AWS IAM | ⏳ |
| `LIVEKIT_*` | Teammate 2 | cloud.livekit.io | ⏳ |
| `ELEVENLABS_API_KEY` / `ELEVENLABS_AGENT_ID` | Teammate 2 | elevenlabs.io after redeeming hackathon coupon | ⏳ |

## Rules

1. **`.env` never gets committed.** `git check-ignore .env` must always return `.env`. If it ever doesn't, `git rm --cached .env` and reset secrets.
2. **No secrets in code, fixtures, README, contracts, screenshots, demo videos.** Only `.env` references the actual values.
3. **No secrets in chat after today.** The Anthropic key + DB password were shared in plain chat once during initial setup. Rotate both **on Sunday 3 May** (post-event).
4. **Production substitution.** `HMAC_SECRET` lives in `.env` for the demo. In any deployed version: MongoDB Queryable Encryption (PRD §4.1).
5. **Atlas IP allowlist** is `0.0.0.0/0` for the venue WiFi today; tighten to specific IPs after the event.

## Rotation checklist (post-hackathon, 3 May 2026)

- [ ] Anthropic — revoke `<current-key-in-local-.env>` and regenerate
- [ ] MongoDB Atlas — change `gaslit-app` password
- [ ] Atlas Network Access — remove `0.0.0.0/0`, add real IPs only
- [ ] Voyage / Fireworks / LangSmith — regenerate keys
- [ ] Teammates rotate NVIDIA / AWS / LiveKit / ElevenLabs

## Loading pattern (canonical)

```python
import os
from dotenv import load_dotenv

load_dotenv()                                    # at process start, once
MONGO_URI = os.environ["MONGODB_URI"]            # raises KeyError if missing — by design
ANTHROPIC = os.environ["ANTHROPIC_API_KEY"]
```

Never write `os.environ.get(KEY, "default-secret")`. If a secret is missing, fail loudly.
