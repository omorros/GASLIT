# GASLIT — Team Plan

> Task split for MongoDB Agentic Evolution Hackathon, London — 2 May 2026.
> Source of truth for scope is `GASLIT_PRD_v6.md`. This file only divides who does what.

---

## Quick map

| Person | Scope |
|---|---|
| Teammate 1 | NVIDIA NeMo Cloud (NemoClaw, NeMo Guardrails, Nemotron) + AWS hosting for Sentinel |
| Teammate 2 | Voice — LiveKit (STT) + ElevenLabs (TTS + Conversational AI) |
| Teammate 3 | Frontend / Next.js 16 — every browser-facing component except voice |
| You (Oriol) | MongoDB Atlas, retrieval pipeline, Anthropic agents (Scribe / Librarian / Forensic Auditor), FastAPI + WebSocket bridge, demo fixtures, MINJA simulator, replay mode, submission |

**Module isolation — only one shared file (`api/main.py`):**

| Person | Owns dirs / files |
|---|---|
| You | `gaslit/schemas.py`, `gaslit/indexes.py`, `gaslit/retrieval/`, `gaslit/provenance/`, `gaslit/agents/scribe.py`, `gaslit/agents/librarian_agent.py`, `gaslit/agents/forensic_auditor.py`, `gaslit/adversary/`, `ws/`, `fixtures/`, most of `scripts/`, `api/main.py` (orchestrator), `api/compliance_export.py` |
| Teammate 1 | `gaslit/agents/sentinel.py`, `gaslit/agents/sentinel_nemotron.py`, `gaslit/guardrails/`, `scripts/kill_sentinel.sh`, `scripts/start_sentinel.sh`, AWS deploy. Ships an `APIRouter` |
| Teammate 2 | `gaslit/voice/`, `frontend/components/voice/`. Ships an `APIRouter` |
| Teammate 3 | `frontend/` everything except `frontend/components/voice/` |

---

## Teammate 1 — NVIDIA NeMo Cloud + AWS

**Owns:** Everything NVIDIA-branded, plus AWS hosting for the Sentinel runtime.

**Files:**
- `gaslit/agents/sentinel.py`
- `gaslit/agents/sentinel_nemotron.py` (Nemotron client + cache)
- `gaslit/guardrails/config.yml` + `prompts.yml`
- `scripts/kill_sentinel.sh`, `scripts/start_sentinel.sh`
- AWS deployment (Lambda or ECS Fargate, `eu-west-2`)

**Tasks in priority order:**

1. **Now:** NVIDIA dev account at `build.nvidia.com`, get API key, test Nemotron from Python. Kick off NemoClaw install in parallel (2.4 GB image — start the download immediately). AWS account ready, Lambda/ECS smoke-test `"hello Sentinel"` in `eu-west-2`.
2. **NemoClaw** (`nemoclaw my-assistant connect`) — **hard 45-min cap**. If not running by then, abort, screenshot the terminal, fall back to MINJA simulator path. Configure the NemoClaw agent to POST the bridging-steps sequence to `http://localhost:8000/api/unprotected-agent`.
3. **NeMo Guardrails wrapping** — `RunnableRails(config, passthrough=True)` with the self-check-input flow from PRD §15. **Write `tests/smoke/test_nemoguardrails_passes_poison.py` first** and verify the MINJA poison message passes through before anything else (if Guardrails blocks it, the demo is dead).
4. **Nemotron 3 Super client** — OpenAI-compatible (`https://integrate.api.nvidia.com/v1`, model `nvidia/nemotron-3-super-120b-a12b`). LRU cache keyed on `(memory_id, drift_bucket)` with 5-min TTL. Test with 100 simulated drift events, verify <40 RPM.
5. **Sentinel agent** — LangGraph `StateGraph`, `MongoDBSaver` v0.3.1 checkpointer. Subscribes to `retrieval_log` Change Stream. Drift score runs in MongoDB aggregation pipeline (no model call). Nemotron called only when `drift_score > 0.62` for explanation. Quarantine writes use idempotency key `(memory_id, drift_bucket, sentinel_run_id)`.
6. **AWS deploy** — Sentinel as Lambda or ECS Fargate in `eu-west-2`. Finalist eligibility gate.
7. Expose endpoints (hand the user a `sentinel_router.py` exporting an `APIRouter`): `POST /api/kill-sentinel`, `POST /api/start-sentinel`.

**Provides:** Sentinel running on AWS · kill/restart endpoints · NeMo Guardrails wrapping the customer-facing agent · NemoClaw terminal visible during demo
**Needs from user:** MongoDB schemas + collections live · `retrieval_log` Change Stream working · librarian retrieval pipeline callable

**Fallbacks:** Nemotron rate-limited → LRU cache + Anthropic Haiku 4.5. NemoClaw fails → screenshot + verbal narrative. NeMo Guardrails install fails → skip wrapping, pitch as roadmap.

---

## Teammate 2 — LiveKit + ElevenLabs (Voice)

**Owns:** All voice I/O — both input (LiveKit STT) and output (ElevenLabs TTS + Conversational AI).

**Files:**
- `gaslit/voice/tts.py` (ElevenLabs Flash v2.5)
- `gaslit/voice/conv_ai.py` (ElevenLabs Conversational AI agent wiring)
- `gaslit/voice/livekit_handler.py` (STT pipeline)
- `frontend/components/voice/LiveKitVoiceInput.tsx`
- `frontend/components/voice/ForensicQAMic.tsx`
- Voice-related FastAPI handlers (export an `APIRouter`)

**Tasks in priority order:**

1. **Now:** LiveKit Cloud project at `cloud.livekit.io`. Get URL + API key. Two rooms: `attacker_room`, `forensic_room`. Verify ElevenLabs Creator tier active via the hackathon coupon. Create the ElevenLabs Conversational AI agent in the dashboard with the system prompt: *"You are the GASLIT Forensic Auditor…"* (PRD §18). Save the `agent_id`.
2. **`@livekit/components-react`** install. Verify mic captures + audio plays in browser before writing components.
3. **`LiveKitVoiceInput.tsx`** — attacker mic in left console header, waveform visible when active. On final transcription: `POST /api/voice-input` with the transcript text.
4. **STT handler** — `POST /api/voice-input` receives transcript → forwards to user's Scribe pipeline.
5. **ElevenLabs Flash v2.5 TTS** — `voice_id="pNInz6obpgDQGcFmaJgB"`, `model_id="eleven_flash_v2_5"`, `mp3_44100_128`. Implement `speak_dossier(text: str) → bytes`. Hook into the dossier component so audio auto-plays 1 s after slide-in.
6. **Forensic Q&A mic** — second LiveKit room (`forensic_room`), mounted under the dossier card. On transcript: `POST /api/forensic-qa` → routes through user's Forensic Auditor → response voiced via ElevenLabs Conversational AI.
7. **Conversational AI widget** — embed the ElevenLabs Conv AI widget in the frontend with the saved `agent_id`. Renders Q&A as a chat thread below dossier.
8. **Fallback:** record `fixtures/attacker.wav` — same speaker, same phrasing as the live demo. Wire keypress trigger so if LiveKit is unstable, audio plays + hardcoded transcript appears. Audience cannot tell.

**Provides:** Two voice components mounted in the UI · `/api/voice-input` and `/api/forensic-qa` handlers · TTS callable from dossier renderer · Conv AI widget · `attacker.wav` fallback
**Needs from user:** Forensic Auditor exposes a function that takes a question + returns dossier-grounded answer text · dossier text payload available when quarantine fires
**Needs from teammate 3:** mounting points for `LiveKitVoiceInput`, `ForensicQAMic`, and the Conv AI widget

**Fallbacks (PRD §15):** LiveKit unstable → `attacker.wav` + hardcoded transcript. Conv AI flaky → keep Flash v2.5 dossier readout, drop interactive Q&A.

---

## Teammate 3 — Frontend (Next.js 16)

**Owns:** Every browser-facing component except the voice ones, the dual-pane operator console, the SVG slides, the LangSmith embed, and the architecture slide.

**Files:**
- `frontend/` (Next.js 16 app)
- All `frontend/components/*.tsx` except the voice subdirectory
- `frontend/hooks/useGaslitEvents.ts`
- `docs/architecture-slide.png`

**Tasks in priority order:**

1. **Now:** Next.js 16 + Tailwind + TypeScript scaffold. Install `@livekit/components-react` so voice teammate's components mount cleanly when they land.
2. **First 30 min — agree the WebSocket event schema with the user in writing in team chat. Lock it.** Format: `{type, payload}` with `type ∈ {drift_update, quarantine, retrieval, agent_status}`. **Do not change after agreement** — both sides build against it independently.
3. **`useGaslitEvents()` hook** — connects to `ws://localhost:8001`, dispatches typed events. Build with mocked events first, don't wait for the bridge.
4. **`DualConsole.tsx`** — split layout, single text input that simultaneously POSTs to `/api/unprotected-agent` and `/api/gaslit-agent`. Stream responses as chat bubbles in each pane.
5. **`FiredBlockedIndicator.tsx`** — RED pulsing border + "FIRED" banner / GREEN solid border + "BLOCKED". **Min 32px font, readable from 5 metres.** CSS `@keyframes`.
6. **`MoneyLedger.tsx`** — left starts $50,000, slot-machine count-down on FIRED → $45,200. Right stays locked. Big numbers.
7. **`DriftGauge.tsx`** — horizontal bar across full width above the dual console. Green → amber at 0.4 → red at 0.62+ with pulse. 0.5 s CSS transition on `drift_update` events.
8. **`MemoryTrustScore.tsx`** — single large 0–100 number. Amber <80, red <60. Polls `/api/trust-score` every 10 s, also updates on `agent_status` WS events.
9. **`DossierRenderer.tsx`** — slides in on `quarantine` event. Monospace card, amber highlights on key fields. Mounts the voice teammate's TTS auto-play hook + Web Audio API waveform.
10. **`TerminalKillRestart.tsx`** — pane with kill/restart buttons → `/api/kill-sentinel`, `/api/start-sentinel`. Shows "⚠ Sentinel offline" / "✓ Sentinel resumed at superstep N" on `agent_status` events.
11. **`MinjaAttackButton.tsx`** — `POST /api/launch-minja-attack`, narration text per step on screen.
12. **`ComplianceExportButton.tsx`** — calls `/api/compliance-export/{quarantine_id}`, triggers JSON download. Place on dossier card.
13. **`CascadeVisualization.tsx`** — static SVG (PRD §12.3), top-right of operator console. ~20 min.
14. **LangSmith trace embed** — iframe of the project URL, always visible.
15. **Architecture slide** — clean four-layer diagram, projector-readable PNG export. Lives in `docs/`.

**Provides:** the entire UI shown to judges
**Needs from user:** WS schema agreed in first 30 min · all backend endpoints listed above · `/api/trust-score`, `/api/memories`
**Needs from teammate 2:** voice components to mount (slot them into `DualConsole` header + dossier card)
**Needs from teammate 1:** kill/restart endpoints

**Fallback (PRD §15):** Frontend breaks → tmux split (raw MongoDB docs left, agent chat right).

---

## You — MongoDB Atlas + Anthropic Agents + Backend Core + Demo Fixtures

**Owns:** Atlas, all data infrastructure, retrieval pipeline, three of the four agents (Scribe / Librarian / Forensic Auditor), FastAPI backend, WebSocket bridge, all demo fixtures + corpus, MINJA simulator, replay mode, submission.

### Atlas + data layer
1. **Atlas setup (now):** verify M10 Dedicated, 8.0.22, `eu-west-2`, `MongoDB .local London Hackathon` org, `Cluster0`. Allowlist `0.0.0.0/0` for venue WiFi. Create DB user `gaslit-app` (readWrite on `gaslit` DB). Smoke-test `$rankFusion` over `$search` sub-pipelines and `$vectorSearch` separately via mongosh. **Invite all three teammates to the hackathon org — NOT your personal org.**
2. `gaslit/schemas.py` — every collection. **`retrieval_log` = REGULAR collection — enforce on line 1** (time-series doesn't support Change Streams; PRD §7).
3. `gaslit/indexes.py` + `scripts/setup_indexes.py` — Vector Search index `memories_vector_idx` (prefilter on `user_id, source_type, quarantined`), Atlas Search index `memories_text_idx`, compound `(memory_id, written_at)`, `(user_id, written_at)`, `(memory_id, ts)` on retrieval_log, TTL on quarantine 30 d / retrieval_log 7 d.

### Retrieval pipeline
4. `gaslit/retrieval/hybrid.py` — parallel `$vectorSearch` (top 50, cosine) + `$rankFusion` over two `$search` sub-pipelines (BM25 on `source_text`, BM25 on `provenance.source_text_hash`). RRF merge in Python with `k=60`. Benchmark: <15 ms.
5. `gaslit/retrieval/contracts.py` — auto-classifier inspecting tool name regex (`delete_*`, `refund_*`, `transfer_*`, `pay_*`, `send_external_*` → high-stakes). Writes `belief_contracts` on startup.
6. `gaslit/retrieval/librarian.py` — full adaptive retrieval: hybrid + contracts + drift filter, logs every retrieval to `retrieval_log`.

### Provenance
7. `gaslit/provenance/hmac.py` — `sign(fields) → str`, `verify(fields, attestation) → bool` (HMAC-SHA256, secret in env).
8. `gaslit/provenance/chain.py` — `get_chain(memory_id) → list[dict]` via `$graphLookup` on `belief_provenance`.

### Agents (Anthropic Sonnet 4.6 direct)
9. `gaslit/agents/scribe.py` — distil via Sonnet 4.6 → Voyage 3 large embed → HMAC sign → atomic 2-collection write to `memories` + `belief_provenance`.
10. `gaslit/agents/librarian_agent.py` — wraps `retrieval/librarian.py`, signature `(query_text, tool_context) → filtered memories`.
11. `gaslit/agents/forensic_auditor.py` — quarantine Change Stream trigger → `provenance/chain.py` → sibling vector search → Sonnet 4.6 dossier composition. Hands dossier text to voice teammate's `tts.py`. LangGraph-checkpointed (`MongoDBSaver`). LangSmith tracing ON.

### FastAPI + WebSocket
12. `api/main.py` — FastAPI on `:8000`. Routes you own:
    - `POST /api/unprotected-agent`, `POST /api/gaslit-agent`
    - `GET /api/memories` (last 50 + drift), `GET /api/trust-score` (0–100 aggregate)
    - `POST /api/launch-minja-attack`
    - `GET /api/compliance-export/{quarantine_id}`
    - `include_router()` from teammate 1's `sentinel_router.py` and teammate 2's voice router. Single seam, single merge file.
13. `ws/bridge.py` — WebSocket server on `:8001`. Subscribes to Change Streams on `memories` (drift updates), `retrieval_log` (inserts), `quarantine` (inserts). Broadcasts JSON to all clients per the locked schema.

### Fixtures + adversary (this is your blocker for the team — get it out fast)
14. **`fixtures/corpus.json` — TOP PRIORITY.** 1,000 memories distilled via Sonnet 4.6, Voyage 3 large embeddings pre-computed for every row. Include 5 poisoned memories matching the demo attack. Commit and ping team.
15. `fixtures/thresholds.json` — simulate 100 retrievals/memory, p99 baseline variance distribution, document threshold ~0.62 with FP rate ~1%.
16. `fixtures/adversary_queries.json` — 20 Fireworks Llama 3.3 70B queries, Voyage embeddings.
17. `gaslit/adversary/minja_canonical.json` — three-turn bridging-steps sequence from arXiv 2503.03704 §4.2, exact paper phrasing.
18. `scripts/load_baseline_corpus.py`, `scripts/calibrate_threshold.py`, `scripts/seed_demo.py` (pre-warms `m_4419` cohort variance to 0.58 — run before each dry run).
19. `gaslit/adversary/live_traffic.py` — Fireworks Llama 3.3 70B live adversary stream during the time-compression window.
20. `gaslit/adversary/minja_simulator.py` — narrated three-turn attack, exposed as `POST /api/launch-minja-attack`.
21. `api/compliance_export.py` — `GET /api/compliance-export/{quarantine_id}` → bundles quarantine doc + `$graphLookup` provenance chain + retrieval audit log → JSON download.

### Replay mode + submission
22. `scripts/replay_server.py` — re-emits WebSocket events from `fixtures/events_replay.json` at 1× speed. Record after first good integration check (~14:00). Ctrl+Shift+R triggers in frontend.
23. **GATE-ZERO — do this within the first hour:** confirm at least one teammate is registered for **MongoDB.local London, Thursday 7 May**. Screenshot in team chat. **No prize eligibility without this.**
24. README, MIT licence, public GitHub repo, hackathon-day disclaimer.
25. Demo dry runs at 16:00, 16:15, 16:30. Submission video recorded at 16:30 (two takes: 1.0× and 1.2×). Submission form filled by 16:50 with all four teammates listed. **Submit at 17:00.**

---

## Coordination contract

**Three contracts to lock in the first 30 min — write them in `docs/contracts.md` and commit:**

1. **WebSocket event schema** — `{type, payload}` shapes for `drift_update`, `quarantine`, `retrieval`, `agent_status`. You + teammate 3.
2. **HTTP API schema** — request/response JSON for every endpoint. All four.
3. **Module function signatures** — `librarian.retrieve(query, tool_context) → list[Memory]`, `provenance.chain.get_chain(memory_id) → list[dict]`, `voice.tts.speak_dossier(text) → bytes`, `forensic_auditor.compose_dossier(quarantine_doc) → str`. You + everyone they unblock.

**Critical sequence (so nobody is blocked):**

| Time | Milestone |
|---|---|
| **T+0** | All four start in parallel — you generate corpus + Atlas setup, teammate 1 starts NemoClaw download + NVIDIA keys, teammate 2 sets up LiveKit, teammate 3 scaffolds Next.js |
| **T+30 min** | All three contracts above committed and locked |
| **T+1 hr** | corpus.json committed (unblocks everyone), schemas + indexes live, NeMo Guardrails wrapping verified passing the poison message, LiveKit mic working in browser |
| **T+1.5 hr** | Scribe writing memories with HMAC, Librarian retrieving, voice STT → backend pipeline working |
| **T+2.5 hr** | Sentinel on Change Streams, drift on live data → **Integration Check #1 (poison spoken → FIRED left, BLOCKED right)** |
| **T+3.5 hr** | All four agents wired, ElevenLabs reads dossier → **Integration Check #2** |
| **T+4 hr** | Conv AI Q&A live, trust score live, SOC2 export wired |
| **T+5 hr** | MINJA simulator, kill-restart verified 5×, replay recorded |
| **T+5.5 hr** | Dry run #1 |
| **T+6 hr (16:30)** | Record submission video |
| **16:50** | Form filled, all four teammates listed |
| **17:00** | **SUBMIT** |

**Branching:** `main` is what you submit. Each person works on `feat/<initials>-<short>`. Merge into `main` only after their integration point passes. Resolve `api/main.py` conflicts by always letting Oriol own the merge — single orchestrator owner.

**Non-negotiables (PRD §15) — never cut:** FIRED/BLOCKED divergence · drift gauge · kill-restart · ElevenLabs dossier audio.

**Cut order if behind at T+3.5 hr:** Conv AI Q&A → NeMo Guardrails wrapping → MINJA simulator → SOC2 export → cascade SVG → trust score.

---

## Hard eligibility gates (PRD §21)

- [ ] MongoDB Atlas Sandbox cluster used (M10, 8.0.22, `eu-west-2`, `MongoDB .local London Hackathon` org, `Cluster0`) — screenshot in `/docs/`
- [ ] At least one team member registered for MongoDB.local London **Thursday 7 May** — **screenshot in team chat ASAP**
- [ ] AWS compute hosts Sentinel (Lambda or ECS in `eu-west-2`)
- [ ] Public GitHub repo, MIT licence
- [ ] All four teammates on submission form
