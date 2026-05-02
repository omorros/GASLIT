# GASLIT — Teammate Quickstart

> Hand this to anyone new on the team. Five minutes to running.

## Prerequisites

- Python 3.10+
- Git
- A copy of `.env` (DM Oriol — the file is gitignored)

## Setup (5 minutes)

```bash
git clone <repo-url> gaslit
cd gaslit
git checkout main

# venv + deps
python -m venv .venv
. .venv/Scripts/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# secrets — paste the .env Oriol DMs you
cp .env.example .env
notepad .env                      # paste real values

# verify Atlas reaches you
python -c "import os; from dotenv import load_dotenv; load_dotenv(); from pymongo import MongoClient; print(MongoClient(os.environ['MONGODB_URI']).admin.command('ping'))"
```

You should see `{'ok': 1.0, ...}`.

## What's already on the cluster

- Database: `gaslit` on `cluster0.g2fje4.mongodb.net` (`eu-west-2`, 8.0.22, M10)
- Six collections, all indexed: `memories`, `belief_provenance`, `retrieval_log`, `quarantine`, `belief_contracts`, `agent_registry`
- Twelve auto-classified belief contracts (6 high_stakes, 4 write, 2 read_only)
- Four agent capability cards (Scribe / Librarian / Sentinel / Forensic Auditor)
- Three Atlas Search indexes building (vector + text + provenance text)

## Running locally

```bash
# starts API on :8002 and WS bridge on :8003
.\scripts\run_all.ps1                          # PowerShell

# or in two separate terminals:
python -m uvicorn api.main:app --port 8002
python ws/bridge.py
```

Smoke check:
```bash
curl http://127.0.0.1:8002/health             # {"status":"ok"}
curl http://127.0.0.1:8002/api/minja-canonical
```

## What each teammate consumes

| You | Read | Touch |
|---|---|---|
| Teammate 1 (NVIDIA / Sentinel) | `retrieval_log` collection (Change Stream), `gaslit/agents/sentinel_fallback.py` for reference logic | `gaslit/agents/sentinel.py`, `gaslit/agents/sentinel_nemotron.py`, `gaslit/guardrails/`, AWS |
| Teammate 2 (Voice) | `gaslit/agents/forensic_auditor.compose_dossier()`, `answer_qa()` | `gaslit/voice/{tts.py,conv_ai.py,livekit_handler.py,router.py}`, `frontend/components/voice/*` |
| Teammate 3 (Frontend) | `docs/contracts.md` — locked WS + HTTP schema | `frontend/` everything except `frontend/components/voice/*` |

## Locked contracts — DO NOT modify

`docs/contracts.md` — frozen at T+30 min, last edit 12:10 to swap ports `8000→8002` (API) and `8001→8003` (WS) due to a local conflict with `radar-api` on Oriol's machine. Wire format unchanged.

## Hot files to re-run after schema/code changes

```bash
python scripts/setup_indexes.py               # idempotent — bootstrap collections + indexes
python scripts/load_baseline_corpus.py        # reload fixtures/corpus.json into memories
python scripts/seed_demo.py                   # pre-warm m_4419 to drift=0.58 before each dry run
python scripts/calibrate_threshold.py         # recompute p99 baseline; writes fixtures/thresholds.json
```

## Demo trigger paths

| What | URL | Trigger |
|---|---|---|
| Full MINJA 3-turn attack | `POST /api/launch-minja-attack` | `MinjaAttackButton.tsx` |
| Live Fireworks adversary stream | `python -m gaslit.adversary.live_traffic --duration 60 --qps 1` | manual / pre-demo cue |
| Compliance JSON download | `GET /api/compliance-export/{quarantine_id}` | `ComplianceExportButton.tsx` |
| Replay the canonical recording | `python scripts/replay_server.py --port 8003` | Ctrl+Shift+R in frontend |

## Where things live

- Code: `gaslit/`
- API: `api/main.py`
- WS bridge: `ws/bridge.py`
- Scripts: `scripts/`
- Fixtures: `fixtures/`
- Docs / contracts: `docs/`

## Help

Anyone stuck — check `docs/contracts.md` first, then ping in team chat. Don't change the contracts, ever.
