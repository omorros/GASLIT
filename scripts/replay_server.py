"""Replay Mode — record a clean WebSocket-event session, re-emit it on demand.

Recording (during a clean live run, with `ws/bridge.py` already up):
  python scripts/replay_server.py --record --duration 90

Replay (instead of `ws/bridge.py`, on the same port):
  python scripts/replay_server.py --port 8001

The frontend hotkey (Ctrl+Shift+R) connects to ws://localhost:8001 either way —
when this server is running instead of `ws/bridge.py`, the audience can't tell.
PRD §15 — "live agent fails on stage → Replay Mode in 5 seconds."
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import websockets

REPLAY_PATH = Path("fixtures") / "events_replay.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(ts: str | None):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


# ─── Replay ───────────────────────────────────────────────────────────
async def replay_handler(events: list[dict]):
    async def handler(ws):
        start_t = time.time()
        anchor = None
        for e in events:
            ts = e.get("ts")
            if anchor is None:
                anchor = _parse(ts)
            target = 0.0
            if anchor:
                cur = _parse(ts)
                if cur:
                    target = (cur - anchor).total_seconds()
            elapsed = time.time() - start_t
            await asyncio.sleep(max(0.0, target - elapsed))
            await ws.send(json.dumps({**e, "ts": _now()}))
    return handler


async def serve_replay(events: list[dict], port: int):
    handler = await replay_handler(events)
    print(f"[replay] serving on ws://0.0.0.0:{port} ({len(events)} events)")
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()  # forever


# ─── Record ───────────────────────────────────────────────────────────
async def record(out: Path, duration_s: int, src: str = "ws://localhost:8001"):
    print(f"[record] connecting to {src} for up to {duration_s}s")
    events: list[dict] = []
    deadline = time.time() + duration_s
    try:
        async with websockets.connect(src) as ws:
            while time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
                    events.append(json.loads(msg))
                except asyncio.TimeoutError:
                    break
                except websockets.ConnectionClosed:
                    break
    except Exception as e:
        print(f"[record] error: {e}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(events))
    print(f"[record] saved {len(events)} events to {out}")


# ─── Main ─────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--duration", type=int, default=90)
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--in", dest="inp", default=str(REPLAY_PATH))
    parser.add_argument("--src", default="ws://localhost:8001",
                        help="When recording: source WS URL")
    args = parser.parse_args()

    if args.record:
        asyncio.run(record(Path(args.inp), args.duration, src=args.src))
        return 0

    path = Path(args.inp)
    if not path.exists():
        print(f"[replay] {path} missing — run with --record first", file=sys.stderr)
        return 2
    events = json.loads(path.read_text())
    asyncio.run(serve_replay(events, args.port))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
