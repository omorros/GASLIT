"""Live adversary traffic — Fireworks Llama 3.3 70B generates diverse
queries that retrieve the planted memory from semantically unrelated topics,
making cohort variance climb visibly during the time-compression demo window.

Two ways to use:
  1. Cached:  loads `fixtures/adversary_queries.json` (deterministic, free).
  2. Live:    calls Fireworks each run (fresh queries, ~$0.01).
"""
from __future__ import annotations

import json
import os
import random
import threading
import time
from pathlib import Path

import httpx
from openai import OpenAI

ADVERSARY_QUERIES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "fixtures" / "adversary_queries.json"
)

GENERATE_SYS = """Generate exactly N short customer queries to a fintech support agent (each under 15 words). Topics must be DIVERSE and UNRELATED — billing, account settings, app features, transaction history, login, statements, fees, transfers, etc.

Output ONE query per line. No numbering, no quotes, no commentary."""


def _fireworks() -> OpenAI:
    return OpenAI(
        base_url=os.environ["FIREWORKS_BASE_URL"],
        api_key=os.environ["FIREWORKS_API_KEY"],
    )


def generate_queries(n: int = 20) -> list[str]:
    client = _fireworks()
    response = client.chat.completions.create(
        model=os.environ["FIREWORKS_MODEL"],
        messages=[{"role": "user", "content": GENERATE_SYS.replace("N", str(n))}],
        max_tokens=600,
        temperature=0.9,
    )
    raw = (response.choices[0].message.content or "").strip()
    out: list[str] = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        ln = ln.lstrip("0123456789.) -").strip().strip('"')
        if ln:
            out.append(ln)
    return out[:n]


def load_canned() -> list[str]:
    if not ADVERSARY_QUERIES_PATH.exists():
        return []
    data = json.loads(ADVERSARY_QUERIES_PATH.read_text())
    if isinstance(data, list):
        # Accept ["query strings"] or [{"query": "..."}]
        return [d if isinstance(d, str) else d.get("query", "") for d in data]
    return []


def stream_traffic(duration_s: int = 60, qps: float = 1.0,
                   *, source: str = "canned") -> int:
    """Send queries at ~qps for duration_s seconds. Returns the number sent."""
    api_base = f"http://127.0.0.1:{os.environ.get('API_PORT', '8000')}"
    queries: list[str]
    if source == "live":
        try:
            queries = generate_queries(20)
        except Exception as e:
            print(f"[live_traffic] Fireworks failed ({e}); falling back to canned")
            queries = load_canned()
    else:
        queries = load_canned()
        if not queries:
            try:
                queries = generate_queries(20)
            except Exception as e:
                print(f"[live_traffic] no canned + Fireworks failed: {e}")
                return 0

    if not queries:
        return 0

    rng = random.Random()
    deadline = time.time() + duration_s
    sent = 0
    print(f"[live_traffic] streaming for {duration_s}s @ {qps} qps "
          f"({len(queries)} unique queries, source={source})")
    with httpx.Client(base_url=api_base, timeout=15.0) as client:
        i = 0
        while time.time() < deadline:
            q = queries[i % len(queries)]
            payload = {
                "message": q,
                "user_id": f"u_traffic_{rng.randint(1000, 9999)}",
                "thread_id": f"t_traffic_{i}",
                "turn_number": 1,
            }
            try:
                client.post("/api/unprotected-agent", json=payload)
                client.post("/api/gaslit-agent", json=payload)
                sent += 1
            except Exception as e:
                print(f"[live_traffic] post error: {e}")
            i += 1
            time.sleep(max(0.0, 1.0 / qps))
    print(f"[live_traffic] sent {sent} queries")
    return sent


def start_traffic(duration_s: int = 60, qps: float = 1.0,
                  source: str = "canned") -> threading.Thread:
    t = threading.Thread(
        target=stream_traffic, args=(duration_s, qps),
        kwargs={"source": source}, daemon=True, name="live-traffic",
    )
    t.start()
    return t


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--qps", type=float, default=1.0)
    parser.add_argument("--source", choices=("canned", "live"), default="canned")
    args = parser.parse_args()
    stream_traffic(args.duration, args.qps, source=args.source)
