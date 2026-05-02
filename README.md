# GASLIT

> **The first defence system that polices what AI agents are allowed to believe.**
> MongoDB Agentic Evolution Hackathon — London — 2 May 2026

GASLIT sits at the **belief layer** between MongoDB and the LLM context window. It catches memory-poisoning attacks (OWASP ASI06, MINJA at NeurIPS 2025) that pass cleanly through OS sandboxes and I/O guardrails because the queries themselves are syntactically benign. The defence is contextual: drift detection on embedding-cohort variance, HMAC-signed provenance, and adaptive retrieval gated by auto-classified belief contracts.

**Themes:** Multi-Agent Collaboration (primary), Prolonged Coordination, Adaptive Retrieval.

## Hackathon-day disclaimer

Everything in this repository was built **between 10:30 BST and 17:00 BST on Saturday 2 May 2026** at CodeNode, London. No prior code was reused. Source: `git log --since=2026-05-02T09:00`.

## Architecture (one screen)

```
NemoClaw OpenShell (NVIDIA)  ── attacker sandbox
        │
NeMo Guardrails              ── I/O layer (passes MINJA)
        │
GASLIT belief layer          ── ← THIS REPO ─ blocks MINJA
        │
Application tools            ── existing
```

Four agents, no agent-to-agent calls — coordination is exclusively through MongoDB collections and Atlas Change Streams:

| Agent | Model | Frequency | Role |
|---|---|---|---|
| Scribe | Claude Sonnet 4.6 | per turn | distillation → Voyage 3 large embedding → HMAC-SHA256 provenance → atomic 2-collection write |
| Librarian | Claude Sonnet 4.6 | per retrieval | auto-classify tool tier → adaptive hybrid retrieval → belief-contract filter → log |
| Sentinel | Nemotron 3 Super 120B | ~5 calls/min | drift detection in MongoDB aggregation → Nemotron explanation only on threshold cross |
| Forensic Auditor | Claude Sonnet 4.6 | burst | `$graphLookup` provenance walk → sibling vector search → dossier → ElevenLabs Conv AI Q&A |

## MongoDB stack — eleven load-bearing features

Atlas Vector Search · Atlas Search (BM25) · `$rankFusion` · `$graphLookup` · Change Streams · TTL indexes · aggregation pipelines · `langgraph-checkpoint-mongodb` v0.3.1 · `langgraph-store-mongodb` · Cloud Backups · compound indexes.

`retrieval_log` is a **regular collection**, not time-series — Change Streams require this.

## Repository map

```
gaslit/      schemas, indexes, retrieval pipeline, agents, provenance, adversary
api/         FastAPI orchestrator (:8000)
ws/          WebSocket bridge — Change Streams to browser (:8001)
frontend/    Next.js 16 operator console
fixtures/    corpus.json (1k memories + Voyage embeddings), thresholds, MINJA payload
scripts/     setup_indexes, load_baseline_corpus, calibrate_threshold, seed_demo, replay_server
docs/        contracts.md (locked), architecture, MongoDB cluster screenshot
tests/       smoke tests
```

## Running locally

```bash
python -m venv .venv
. .venv/Scripts/activate     # Windows / PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env         # fill in keys
python scripts/setup_indexes.py
python scripts/load_baseline_corpus.py
uvicorn api.main:app --port 8002 &
python ws/bridge.py &     # listens on :8003
cd frontend && npm install && npm run dev
```

## Submission

- Hackathon: https://cerebralvalley.ai/e/mongo-db-london-hackathon/hackathon/submit
- Demo video (60s): `docs/demo.mp4`
- All four teammates listed on the submission form.

## Licence

MIT.

## References

- OWASP Top 10 for Agentic Apps 2026 — ASI06: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- MINJA paper (Dong et al., NeurIPS 2025): https://arxiv.org/abs/2503.03704
