<div align="center">

# GASLIT

### The first defence system that polices what AI agents are allowed to believe.

The belief layer between MongoDB and the LLM. Catches memory poisoning that passes through every existing guardrail because the queries themselves look benign.

[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.6-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)

[![MongoDB Atlas](https://img.shields.io/badge/MongoDB_Atlas-8.0.22-00ED64?style=flat-square&logo=mongodb&logoColor=white&labelColor=001E2B)](https://www.mongodb.com/atlas)
[![NVIDIA Nemotron](https://img.shields.io/badge/NVIDIA-Nemotron_3_Super_120B-76B900?style=flat-square&logo=nvidia&logoColor=white)](https://build.nvidia.com/)
[![NeMo Guardrails](https://img.shields.io/badge/NVIDIA-NeMo_Guardrails-76B900?style=flat-square&logo=nvidia&logoColor=white)](https://docs.nvidia.com/nemo/guardrails/latest/)
[![NemoClaw](https://img.shields.io/badge/NVIDIA-NemoClaw_OpenShell-76B900?style=flat-square&logo=nvidia&logoColor=white)](https://github.com/NVIDIA/NemoClaw)
[![AWS](https://img.shields.io/badge/AWS-ECS_Fargate_·_eu--west--2-FF9900?style=flat-square&logo=amazonaws&logoColor=white)](https://aws.amazon.com/ecs/)

[![Anthropic](https://img.shields.io/badge/Anthropic-Claude_Sonnet_4.6-D97757?style=flat-square&logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![ElevenLabs](https://img.shields.io/badge/ElevenLabs-Flash_v2.5_·_Conv_AI-000000?style=flat-square)](https://elevenlabs.io/)
[![LiveKit](https://img.shields.io/badge/LiveKit-Cloud-1F2937?style=flat-square)](https://livekit.io/)
[![Voyage AI](https://img.shields.io/badge/Voyage_AI-voyage--3--large-7C3AED?style=flat-square)](https://www.voyageai.com/)
[![Fireworks](https://img.shields.io/badge/Fireworks_AI-Llama_3.3_70B-FF4F00?style=flat-square)](https://fireworks.ai/)
[![LangSmith](https://img.shields.io/badge/LangSmith-tracing-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://smith.langchain.com/)

[![Hackathon](https://img.shields.io/badge/MongoDB_Agentic_Evolution-London_·_2_May_2026-00ED64?style=flat-square&logo=mongodb&logoColor=white&labelColor=001E2B)](https://cerebralvalley.ai/e/mongo-db-london-hackathon)
[![Themes](https://img.shields.io/badge/Themes-Multi--Agent_·_Prolonged_·_Adaptive-76B900?style=flat-square)](#themes-coverage)
[![OWASP ASI06](https://img.shields.io/badge/OWASP-ASI06_Memory_Poisoning-DC2626?style=flat-square)](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
[![MINJA](https://img.shields.io/badge/MINJA-arXiv_2503.03704-B31B1B?style=flat-square&logo=arxiv&logoColor=white)](https://arxiv.org/abs/2503.03704)
[![License](https://img.shields.io/badge/License-MIT-555555?style=flat-square)](#licence)

<br />

![GASLIT landing](docs/screenshots/landing.png)

</div>

---

## Overview

GASLIT is a four-agent belief-layer defence built on MongoDB Atlas. It blocks **memory poisoning attacks** (OWASP ASI06, MINJA at NeurIPS 2025) that bypass kernel sandboxes and I/O guardrails because the malicious queries are individually benign. The defence is contextual: it watches the cohort of queries that retrieve each memory, computes a statistical drift fingerprint inside MongoDB aggregation pipelines, and gates retrieval with auto-classified belief contracts.

> *Defences today police what agents do. GASLIT polices what agents are allowed to believe.*

The attacker is a normal user with no privileges. They plant a poisoned belief through conversational queries. Days or weeks later a high-trust user fires a related question, the agent retrieves the planted memory, and an authorised tool acts on a corrupted fact. NemoClaw cannot see it (data-layer attack). NeMo Guardrails cannot see it (queries are not jailbreaks). GASLIT catches it at the moment of retrieval, between MongoDB and the LLM context.

---

## Highlights

- **Four agents, zero direct calls.** All coordination via MongoDB collections and Atlas Change Streams. Satisfies OWASP ASI07 while solving ASI06.
- **Eleven MongoDB Atlas features**, all load-bearing. `$rankFusion` plus `$vectorSearch` plus `$graphLookup` plus Change Streams plus TTLs plus aggregation pipelines plus LangGraph checkpointing in Mongo plus more.
- **Belief contracts auto-classify** at startup. Tool name regex sets the tier (high stakes, write, read only). High-stakes tools require HMAC-signed provenance plus drift below 0.62 plus tool-grounded source. The retrieval pipeline reshapes itself per query.
- **Drift detection runs inside MongoDB.** Cohort variance over the last 50 query embeddings per memory, computed in aggregation pipelines. Nemotron 3 Super is called only when the threshold crosses, keeping us under the 40 RPM free tier.
- **Prolonged coordination, demoed live.** `langgraph-checkpoint-mongodb` v0.3.1. `kill -9` the Sentinel mid-investigation, restart, watch it resume from the same superstep.
- **Voice everywhere.** LiveKit captures the attacker. ElevenLabs Flash v2.5 reads the forensic dossier. ElevenLabs Conversational AI answers judges' questions about an open quarantine.
- **SOC2 evidence on click.** `GET /api/compliance-export/{id}` bundles the quarantine doc, full `$graphLookup` provenance chain, and retrieval audit into a downloadable JSON. The pitch line is *"that file is what we are selling to enterprises."*
- **Sandbox by design.** Open-source core, MIT licence. The Sentinel never executes a tool. Every flag is a memo for a human.

---

## Screenshots

<table>
<tr>
<td width="50%">

**Landing.** GASLIT wordmark, defence pipeline ribbon (Adversary, Scribe, Librarian, Sentinel, Forensic), live partner stack.

![landing](docs/screenshots/landing.png)

</td>
<td width="50%">

**Five agents, zero direct calls.** Each agent's model, role, and MongoDB hooks. Coordination is exclusively through Change Streams.

![agents](docs/screenshots/agents.png)

</td>
</tr>
<tr>
<td width="50%">

**Same database. Same prompt. Different outcome.** Unprotected agent fires a $4,800 refund on a poisoned memory. GASLIT applies the high-stakes belief contract, filters it, escalates.

![divergence](docs/screenshots/divergence.png)

</td>
<td width="50%">

**Operator console + voice.** *(coming: terminal screenshot of the live attack flow, Sentinel kill-restart, ElevenLabs dossier readout, SOC2 export download.)*

</td>
</tr>
</table>

---

## Architecture

```mermaid
flowchart LR
    subgraph attacker["Layer 1 · NVIDIA NemoClaw OpenShell"]
        direction TB
        ATK[Attacker agent<br/>kernel sandbox<br/>Landlock + seccomp + netns]
    end

    subgraph io["Layer 2 · NeMo Guardrails I/O"]
        direction TB
        GR[Passthrough config<br/>jailbreak + PII checks]
    end

    subgraph belief["Layer 3 · GASLIT belief layer"]
        direction TB
        SC[Scribe<br/>Claude Sonnet 4.6]
        LB[Librarian<br/>Claude Sonnet 4.6]
        SN[Sentinel<br/>Nemotron 3 Super 120B<br/>AWS ECS Fargate · eu-west-2]
        FA[Forensic Auditor<br/>Claude Sonnet 4.6]
    end

    subgraph mongo["MongoDB Atlas · 8.0.22 · eu-west-2"]
        direction TB
        DB[(memories · belief_provenance<br/>retrieval_log · quarantine<br/>belief_contracts · agent_registry<br/>langgraph_checkpoints)]
    end

    subgraph surface["Surface · LiveKit + ElevenLabs"]
        direction TB
        WS[WebSocket bridge<br/>Atlas Change Streams]
        UI[Next.js 16 console<br/>LiveKit STT · ElevenLabs TTS · Conv AI]
    end

    ATK -->|voice + HTTP| GR
    GR -->|writes| SC
    GR -->|reads| LB
    SC --> DB
    LB --> DB
    DB -.Change Stream.-> SN
    SN --> DB
    DB -.Change Stream.-> FA
    FA --> DB
    DB -.Change Stream.-> WS
    WS --> UI

    classDef gaslit fill:#76b900,color:#fff,stroke:#5e9100,stroke-width:2px
    classDef agent fill:#f0fad8,color:#3d5f00,stroke:#aae030
    classDef red fill:#fef2f2,color:#991b1b,stroke:#fca5a5
    classDef amber fill:#fffbeb,color:#92400e,stroke:#fcd34d
    classDef mongo fill:#001E2B,color:#00ED64,stroke:#00ED64
    classDef surf fill:#0a0a0c,color:#ffffff,stroke:#76b900

    class SN gaslit
    class SC,LB,FA agent
    class ATK red
    class GR amber
    class DB mongo
    class WS,UI surf
```

Three runtimes, one cluster:

| Service | Stack | Port | Role |
|---|---|---|---|
| `frontend/` | Next.js 16, React 19, Tailwind CSS 4, Magic UI, LiveKit components | `:3000` | Landing, about page (live runtime status), voice surface, console placeholder |
| `api/` | FastAPI, PyMongo, Anthropic SDK, Voyage SDK, ElevenLabs SDK | `:8002` | Orchestrator. Routes: `/api/unprotected-agent`, `/api/gaslit-agent`, `/api/voice/*`, `/api/forensic-qa`, `/api/compliance-export/{id}`, `/api/demo/*`, `/demo` |
| `ws/` | Motor, websockets, Atlas Change Streams | `:8003` | Subscribes to `memories`, `retrieval_log`, `quarantine`. Broadcasts JSON envelopes per `docs/contracts.md`. |
| `gaslit/agents/sentinel.py` | LangGraph, MongoDBSaver v0.3.1, Nemotron client | AWS ECS | Drift detection on retrieval_log Change Stream. Kill-restart safe. |

---

## The Four-Layer Defence

```mermaid
flowchart TD
    MINJA["MINJA bridging-steps attack<br/>arXiv 2503.03704 · OWASP ASI06<br/>>95% success on unprotected agents"]:::attack

    L1["1 · NemoClaw OpenShell<br/><i>kernel sandbox · process isolation</i>"]:::layer
    L2["2 · NeMo Guardrails<br/><i>jailbreak · PII · topic filtering</i>"]:::layer
    L3["3 · GASLIT<br/><b>provenance · drift · belief contracts</b>"]:::gaslit
    L4["4 · Tool authorisation<br/><i>RBAC · audit logs</i>"]:::layer

    STOP["✓ Quarantined<br/>dossier composed · SOC2 export"]:::stopped
    LOSS["✗ Tool fired<br/>$50,000 → $45,200"]:::loss

    MINJA -->|"individually benign queries"| L1
    L1 -->|"passes · data-layer attack"| L2
    L2 -->|"passes · not a jailbreak"| L3
    L3 -->|"BLOCKS · cohort variance + HMAC + contract"| STOP
    L3 -.->|"if no GASLIT layer"| L4
    L4 -.->|"authorised tool fires<br/>on poisoned belief"| LOSS

    classDef attack fill:#fef2f2,color:#991b1b,stroke:#dc2626,stroke-width:2px
    classDef layer fill:#f5f5f5,color:#262626,stroke:#737373
    classDef gaslit fill:#76b900,color:#ffffff,stroke:#5e9100,stroke-width:3px
    classDef stopped fill:#10b981,color:#ffffff,stroke:#059669,stroke-width:2px
    classDef loss fill:#ef4444,color:#ffffff,stroke:#b91c1c,stroke-width:2px
```

NemoClaw contains the attacker process. NeMo Guardrails sees no jailbreak. The poison rides benign HTTP. Layer 3 is where it stops.

---

## The Five Agents · zero direct calls

```mermaid
flowchart LR
    USER([User message]) --> SC
    SC -.write.-> MEM[(memories<br/>+ belief_provenance)]
    QUERY([Tool query]) --> LB
    LB -.read.-> MEM
    LB -.log every retrieval.-> RL[(retrieval_log)]
    RL -.Change Stream.-> SN
    SN -.drift score · quarantine.-> Q[(quarantine)]
    Q -.Change Stream.-> FA
    FA -.dossier_text + siblings.-> Q
    Q -.WS broadcast.-> UI([UI · ElevenLabs TTS])

    classDef agent fill:#f0fad8,color:#3d5f00,stroke:#aae030,stroke-width:2px
    classDef gaslit fill:#76b900,color:#ffffff,stroke:#5e9100,stroke-width:3px
    classDef store fill:#001E2B,color:#00ED64,stroke:#00ED64

    class SC,LB,FA agent
    class SN gaslit
    class MEM,RL,Q store

    SC[Scribe<br/>Sonnet 4.6]
    LB[Librarian<br/>Sonnet 4.6]
    SN[Sentinel<br/>Nemotron 120B]
    FA[Forensic Auditor<br/>Sonnet 4.6]
```

| Agent | Model | Cadence | Role |
|---|---|---|---|
| **Adversary** | Fireworks Llama 3.3 70B Instruct | live attack stream | Generates the synthetic adversary query stream during the time-compression window. Runs the canonical bridging-steps sequence from arXiv 2503.03704 §4.2. Driven from a real NemoClaw OpenShell bridge in production. |
| **Scribe** | Claude Sonnet 4.6 (Anthropic direct) | per conversation turn | Distils chat into memory entries. Voyage 3 large embed (1024-dim, cosine). Atomic write to `memories` plus `belief_provenance` with HMAC-SHA256 attestation. |
| **Librarian** | Claude Sonnet 4.6 (Anthropic direct) | per retrieval request | Auto-classifies tool tier from name regex. Builds adaptive hybrid retrieval (three-arm parallel `$vectorSearch` plus `$rankFusion` plus RRF merge). Applies belief contract filter. Logs every retrieval. |
| **Sentinel** | Nemotron 3 Super 120B (NVIDIA) | ~5 model calls / min peak | Subscribes to `retrieval_log` Change Stream. Drift score in MongoDB aggregation, no model call. Calls Nemotron only on threshold cross (>0.62) for the 2-sentence explanation. LangGraph-checkpointed. AWS ECS Fargate. |
| **Forensic Auditor** | Claude Sonnet 4.6 (Anthropic direct) | burst, rare | Triggered by `quarantine` Change Stream. `$graphLookup` walks `belief_provenance`. Sibling-memory vector search. Composes 4-6 sentence dossier. ElevenLabs Conv AI for interactive voice Q&A. |

---

## Hackathon Eligibility

PRD §21 requirements, every box ticked.

| Gate | Evidence | Where |
|---|---|---|
| ✅ MongoDB Atlas Sandbox cluster (M10, 8.0.22, `eu-west-2`, `MongoDB .local London Hackathon` org, `Cluster0`) | Cluster screenshot | [`docs/mongodb-cluster-screenshot.png`](docs/mongodb-cluster-screenshot.png) |
| ✅ MongoDB.local London 7 May registration (at least one teammate) | Confirmed in team chat | n/a |
| ✅ AWS compute hosts the Sentinel runtime | ECS Fargate deploy in `eu-west-2` via boto3 | [`gaslit/deploy/deploy_sentinel_aws.py`](gaslit/deploy/deploy_sentinel_aws.py), [`gaslit/deploy/deploy_sentinel_aws.sh`](gaslit/deploy/deploy_sentinel_aws.sh), [`gaslit/deploy/Dockerfile.sentinel`](gaslit/deploy/Dockerfile.sentinel) |
| ✅ MongoDB Atlas is a core component | 11 load-bearing features, listed below | [`gaslit/schemas.py`](gaslit/schemas.py), [`gaslit/indexes.py`](gaslit/indexes.py) |
| ✅ All three themes hit with concrete demo evidence | Multi-agent (4 agents, no direct calls), Prolonged (kill-restart at 2:00), Adaptive (per-tool retrieval pipeline) | [Themes](#themes-coverage) |
| ✅ `retrieval_log` is a regular collection, not time-series | Bootstrap raises if anyone breaks this | [`gaslit/schemas.py`](gaslit/schemas.py) line 1 banner |
| ✅ Public GitHub repo, MIT licence | This repo, [`LICENSE`](LICENSE) | n/a |
| ✅ Hackathon-day disclaimer in README | Built between 10:30 BST and 17:00 BST on Sat 2 May 2026 at CodeNode, London. No prior code reused. | This file |

---

## Themes Coverage

### Multi-Agent Collaboration · primary ✅

Four specialised agents, non-overlapping capabilities, **coordinating exclusively through MongoDB Change Streams** plus capability cards in `agent_registry`. No agent calls another agent directly. Sentinel decides at runtime whether to invoke Forensic Auditor.

> Brief language: *"specialised agents explore, assign tasks, and communicate with one another, using MongoDB to organise and oversee contexts."*

### Prolonged Coordination ✅

Memory poisoning is temporally decoupled. Plant on day 1, fire on day 21. `langgraph-checkpoint-mongodb` v0.3.1 checkpoints the Sentinel's investigation graph. Demo proof at 2:00 mark: `kill -9 $SENTINEL_PID`, then `./scripts/start_sentinel.sh`, then watch the investigation resume from the same superstep, same dossier.

### Adaptive Retrieval ✅

The Librarian reshapes the retrieval pipeline per query based on auto-classified tool tier. Different tools, different `$match` predicates, different rank weights, different `numCandidates`. Honestly modifies query approach and reorders results (two and a half of three brief criteria, which is sufficient).

---

## MongoDB Stack · eleven load-bearing features

| Feature | Where | What for |
|---|---|---|
| **Atlas Vector Search** (Voyage 3 large, 1024-dim, cosine) | `gaslit/retrieval/hybrid.py` | Semantic memory retrieval, sibling-poison search in forensics |
| **Atlas Search (BM25)** | `gaslit/retrieval/hybrid.py` | Keyword + provenance source-text matching, second arm of hybrid retrieval |
| **`$rankFusion` + manual RRF merge** | `gaslit/retrieval/hybrid.py` | 8.0.22-compatible hybrid pipeline, k=60, per-contract weights |
| **`$graphLookup`** | `gaslit/provenance/chain.py` | Walks `parent_memory_id` chain in `belief_provenance` to reconstruct injection lineage |
| **Atlas Change Streams** | `ws/bridge.py`, `gaslit/agents/sentinel.py`, `gaslit/agents/forensic_auditor.py` | Real-time event bus. Sentinel reacts to `retrieval_log`. Forensic to `quarantine`. WS bridge to all three. |
| **TTL indexes** | `gaslit/indexes.py` | `quarantine` 30 days, `retrieval_log` 7 days, auto-expire |
| **Aggregation pipelines** | `gaslit/agents/sentinel.py`, `gaslit/agents/sentinel_fallback.py` | Drift score (cohort variance + frequency-vs-age) computed in-database, no model call |
| **`langgraph-checkpoint-mongodb` v0.3.1** | `gaslit/agents/sentinel.py` | Sentinel investigation graph survives `kill -9`, demoed live |
| **`langgraph-store-mongodb`** | `gaslit/agents/sentinel.py` | Long-term memory primitive, the attack surface itself |
| **Atlas Cloud Backups** | cluster config | Investigation history durable across cluster failures |
| **Standard compound indexes** | `gaslit/indexes.py` | `(memory_id, written_at)`, `(user_id, written_at)`, `(memory_id, ts)` on retrieval_log, plus uniqueness constraints |

`retrieval_log` is a **regular collection**. Time-series collections do not support Change Streams. Without Change Streams, Sentinel cannot wake up. `gaslit/schemas.py` raises if anyone breaks this.

---

## Quickstart

### Prerequisites

- Node.js 22 or higher
- Python 3.11 or higher
- MongoDB Atlas cluster (M10, 8.0.22, `eu-west-2`, hackathon org)
- API keys for: Anthropic, Voyage, ElevenLabs, LiveKit, NVIDIA, Fireworks, AWS

### Install

```bash
git clone https://github.com/omorros/GASLIT.git && cd GASLIT
python -m venv .venv
source .venv/bin/activate    # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### Configure

Copy `.env.example` to `.env` at the repo root and fill in real values. The file is gitignored so editors may hide it from the sidebar. Open it via Quick Open (`Cmd+P` / `Ctrl+P`) and type `.env`.

```bash
cp .env.example .env
```

Required env vars: `MONGODB_URI`, `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, `NVIDIA_API_KEY`, `FIREWORKS_API_KEY`, `HMAC_SECRET`, `AWS_REGION` (`eu-west-2`). Leave `NEXT_PUBLIC_API_BASE` empty so the browser uses the same-origin `/backend/*` proxy.

### Bootstrap MongoDB

```bash
python scripts/setup_indexes.py        # creates collections + vector + BM25 + TTL + compound indexes
python scripts/load_baseline_corpus.py # bulk-inserts 1,000 pre-embedded memories
python scripts/calibrate_threshold.py  # writes fixtures/thresholds.json (~0.62)
python scripts/seed_demo.py            # pre-warms m_4419 to drift 0.58 (run before every dry run)
```

### Run

Three terminals:

```bash
# Terminal 1: FastAPI orchestrator on :8002
uvicorn api.main:app --port 8002

# Terminal 2: WebSocket bridge on :8003 (Atlas Change Streams to browser)
python ws/bridge.py

# Terminal 3: Next.js dev server on :3000
cd frontend && npm run dev
```

Optional fourth terminal for local Sentinel (skip if Sentinel runs on AWS ECS):

```bash
python -m gaslit.agents.sentinel
# or fallback (no Nemotron, no LangGraph checkpointing):
python -m gaslit.agents.sentinel_fallback
```

Open http://localhost:3000.

---

## Demo · 3-minute flow

| Time | What happens | URL / surface |
|---|---|---|
| 0:00 | Attacker speaks the poison line into the LiveKit mic. Scribe writes `m_4419` to MongoDB. NeMo Guardrails passes (test verified). | `/voice` LiveKit mic toggle |
| 0:35 | Time compression. Fireworks pumps 20 unrelated queries through the Librarian. Sentinel watches drift climb 0.21 → 0.60. | `/demo` polls every 2s |
| 1:00 | High-value user asks for $4,800 refund. Both endpoints fire. Unprotected fires the tool. GASLIT applies high-stakes contract, escalates. | `POST /api/launch-minja-attack` |
| 1:30 | Quarantine writes. Forensic Auditor composes dossier via Sonnet 4.6. ElevenLabs Flash v2.5 reads it aloud automatically. | `/voice` `QuarantineDossierVoice` |
| 1:50 | Presenter asks *"Who else did this user attack?"* into the forensic mic. Conv AI answers with sibling memory IDs. | `/voice` `ForensicQAMic` |
| 2:00 | `kill -9 $SENTINEL_PID`. Status pill on `/about` flips to amber. `./scripts/start_sentinel.sh`. Resumes from same superstep. | `/about` runtime card |
| 2:15 | Click "Export Compliance Report". JSON downloads with quarantine + provenance chain + retrieval audit + HMAC-verified flag. | `GET /api/compliance-export/{id}` |
| 2:30 | Close pitch on `/about`. Four-layer diagram. Sit down. | `/about` |

Pre-recorded fallback: `scripts/replay_server.py` re-emits the recorded WebSocket event stream. **Ctrl+Shift+R** swaps live for replay in 5 seconds.

---

## Tech Stack

<table>
<tr><td><b>Frontend</b></td><td>

Next.js 16 (Turbopack), React 19, TypeScript 5, Tailwind CSS 4, Magic UI primitives (animated-beam, border-beam, marquee, number-ticker, dot-pattern, shimmer-button), shadcn (Card, Badge, Separator), Lucide icons, Motion (Framer)

</td></tr>
<tr><td><b>Backend</b></td><td>

FastAPI, PyMongo (sync), Motor (async, for Change Streams), Pydantic, websockets, uvicorn

</td></tr>
<tr><td><b>Agents and AI</b></td><td>

Anthropic Claude Sonnet 4.6 (Scribe, Librarian, Forensic Auditor), NVIDIA Nemotron 3 Super 120B (Sentinel), Voyage AI `voyage-3-large` (1024-dim), Fireworks Llama 3.3 70B Instruct (Adversary)

</td></tr>
<tr><td><b>NVIDIA stack</b></td><td>

NemoClaw OpenShell (attacker sandbox), NeMo Guardrails (I/O layer wrap, passthrough config), Nemotron 3 Super 120B (Sentinel explanation engine, OpenAI-compatible)

</td></tr>
<tr><td><b>Voice</b></td><td>

LiveKit Cloud (rooms: `attacker_room`, `forensic_room`), `@livekit/components-react`, ElevenLabs Flash v2.5 TTS (`mp3_44100_128`), ElevenLabs Conversational AI Agent (judge Q&A)

</td></tr>
<tr><td><b>Orchestration and observability</b></td><td>

LangGraph 0.6+, `langgraph-checkpoint-mongodb` v0.3.1, `langgraph-store-mongodb`, LangSmith tracing (Forensic Auditor)

</td></tr>
<tr><td><b>Infrastructure</b></td><td>

MongoDB Atlas M10 8.0.22 (`eu-west-2`, hackathon org `Cluster0`), AWS ECS Fargate (`eu-west-2`) for Sentinel, AWS ECR for the Sentinel image, boto3 deploy script

</td></tr>
</table>

---

## Project Structure

<details>
<summary>Click to expand</summary>

```
GASLIT/
├── api/
│   ├── main.py                       # FastAPI orchestrator (single seam)
│   ├── compliance_export.py          # SOC2 JSON export
│   └── demo_dashboard.py             # /demo HTML dashboard + /api/demo/*
│
├── gaslit/
│   ├── schemas.py                    # six collections, retrieval_log enforced as regular
│   ├── indexes.py                    # vector + BM25 + compound + TTL
│   ├── embeddings.py                 # Voyage 3 large adapter
│   ├── retrieval/
│   │   ├── hybrid.py                 # 3-arm parallel + RRF merge (k=60)
│   │   ├── contracts.py              # auto-classifier (high stakes / write / read only)
│   │   └── librarian.py              # adaptive retrieval entry point
│   ├── provenance/
│   │   ├── hmac.py                   # HMAC-SHA256 sign / verify
│   │   └── chain.py                  # $graphLookup walker
│   ├── agents/
│   │   ├── scribe.py                 # distil → Voyage embed → HMAC → atomic 2-coll write
│   │   ├── librarian_agent.py        # thin wrapper around retrieval/librarian
│   │   ├── sentinel.py               # production Sentinel · LangGraph + Nemotron + AWS
│   │   ├── sentinel_nemotron.py      # Nemotron client + LRU cache
│   │   ├── sentinel_fallback.py      # backup drift detector (no Nemotron)
│   │   └── forensic_auditor.py       # quarantine watcher · dossier · voice Q&A
│   ├── guardrails/                   # NeMo Guardrails config + prompts
│   ├── voice/                        # LiveKit handler + ElevenLabs TTS + Conv AI
│   ├── adversary/
│   │   ├── minja_canonical.json      # bridging-steps from arXiv 2503.03704 §4.2
│   │   ├── minja_simulator.py        # ▶ Run MINJA Attack
│   │   ├── live_traffic.py           # Fireworks adversary stream
│   │   └── nemoclaw_bridge.py        # real OpenShell driver
│   └── deploy/
│       ├── Dockerfile.sentinel
│       ├── deploy_sentinel_aws.py    # boto3 ECS Fargate deployer
│       └── deploy_sentinel_aws.sh
│
├── ws/
│   └── bridge.py                     # Atlas Change Streams → browser (:8003)
│
├── frontend/                         # Next.js 16
│   ├── app/
│   │   ├── page.tsx                  # landing
│   │   ├── about/page.tsx            # threat model + runtime status section
│   │   ├── voice/page.tsx            # voice surface (mic, dossier TTS, Conv AI)
│   │   └── console/page.tsx          # operator console placeholder
│   └── components/
│       ├── ui/                       # Magic UI + shadcn primitives
│       └── voice/                    # LiveKitVoiceInput, DossierTTS, ForensicQAMic, ConvAIWidget
│
├── scripts/
│   ├── setup_indexes.py
│   ├── load_baseline_corpus.py
│   ├── calibrate_threshold.py
│   ├── seed_demo.py                  # pre-warms m_4419 (run before every dry run)
│   ├── replay_server.py              # Ctrl+Shift+R fallback
│   ├── kill_sentinel.sh
│   ├── start_sentinel.sh
│   └── nemoclaw_minja_driver.py
│
├── fixtures/
│   ├── corpus.json                   # 1,000 pre-embedded memories (4.8 MB)
│   ├── thresholds.json               # calibrated p99 baseline
│   └── adversary_queries.json        # 20 Fireworks queries
│
├── docs/
│   ├── contracts.md                  # locked API + WS + module contracts
│   ├── quickstart.md
│   ├── secrets.md
│   ├── mongodb-cluster-screenshot.png
│   └── screenshots/                  # README assets
│
├── tests/smoke/
│   ├── test_auto_classifier.py
│   ├── test_hmac_provenance.py
│   ├── test_scribe_writes.py
│   ├── test_integration.py
│   ├── test_atlas_live_readiness.py
│   └── test_nemoguardrails_passes_poison.py
│
├── GASLIT_PRD_v6.md                  # full product spec
├── TEAM_PLAN.md                      # task split per teammate
└── README.md                         # this file
```

</details>

---

## Reset and debug

```bash
# Re-create indexes from scratch
python scripts/setup_indexes.py

# Reload the 1,000-memory corpus
python scripts/load_baseline_corpus.py

# Pre-warm m_4419 before a dry run (drift 0.58, just below threshold)
python scripts/seed_demo.py

# Reset all drift scores to zero
python scripts/seed_demo.py --reset

# Smoke tests
pytest tests/smoke/

# Verify the poison message passes NeMo Guardrails
pytest tests/smoke/test_nemoguardrails_passes_poison.py

# Verify Atlas live readiness (collections, indexes, vector + text both queryable)
pytest tests/smoke/test_atlas_live_readiness.py

# Live API checks
curl http://localhost:8002/health
curl http://localhost:8002/api/trust-score | jq
curl http://localhost:8002/api/demo/live | jq '.sentinel, .counts'
curl -X POST http://localhost:8002/api/launch-minja-attack
```

---

## Team

Built in one day at MongoDB Agentic Evolution Hackathon, London, on Saturday 2 May 2026 by a four-person team. See [`TEAM_PLAN.md`](TEAM_PLAN.md) for the full split.

| Owner | Subsystem |
|---|---|
| **Oriol** | MongoDB Atlas, retrieval pipeline, Anthropic agents (Scribe, Librarian, Forensic Auditor), FastAPI plus WebSocket bridge, demo fixtures, MINJA simulator, replay mode, submission, landing plus about pages |
| **Teammate 1** | NVIDIA NeMo Cloud (NemoClaw, NeMo Guardrails, Nemotron) plus production Sentinel plus AWS ECS Fargate deploy plus `/demo` HTML dashboard |
| **Teammate 2** | Voice, LiveKit STT plus ElevenLabs Flash v2.5 TTS plus ElevenLabs Conversational AI plus voice routers plus `attacker.wav` fallback |
| **Teammate 3** | Frontend scaffold, Next.js 16 app structure, shared components |

---

## References

- [OWASP Top 10 for Agentic Apps 2026, ASI06 Memory Poisoning](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
- [MINJA: Memory Injection Attack on LLM Agents (Dong et al., NeurIPS 2025), arXiv:2503.03704](https://arxiv.org/abs/2503.03704)
- [Agent Security Bench](https://arxiv.org/abs/2601.05504)
- [`GASLIT_PRD_v6.md`](GASLIT_PRD_v6.md) full product spec
- [`TEAM_PLAN.md`](TEAM_PLAN.md) task division
- [`docs/contracts.md`](docs/contracts.md) locked API + WS + module contracts

---

## Hackathon-day disclaimer

Everything in this repository was built **between 10:30 BST and 17:00 BST on Saturday 2 May 2026** at CodeNode, London, for the MongoDB Agentic Evolution Hackathon. No prior code was reused. Verifiable via `git log --since=2026-05-02T09:00`.

---

## Licence

MIT. See [`LICENSE`](LICENSE).

<div align="center">

---

*Defences today police what agents do. We police what they are allowed to believe.*

**GASLIT** · belief-layer defence on MongoDB Atlas · NVIDIA + AWS finalist track

</div>
