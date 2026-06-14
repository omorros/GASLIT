#!/usr/bin/env python3
"""POST /api/livekit/token and verify JWT shape (no secret output)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> None:
    base = os.environ.get("NEXT_PUBLIC_API_BASE", "http://127.0.0.1:8002").rstrip("/")
    url = f"{base}/api/livekit/token"
    body = json.dumps({"room": "attacker_room", "identity": "smoke-test"}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:500], file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print("Request failed:", e, file=sys.stderr)
        sys.exit(1)

    token = data.get("token", "")
    wss = data.get("url", "")
    room = data.get("room", "")
    ok = isinstance(token, str) and token.count(".") == 2 and wss.startswith("wss://")
    print("livekit_token_ok:", ok)
    print("room:", room)
    print("url_host:", wss.split("//")[-1][:40] + "…" if len(wss) > 40 else wss)
    print("jwt_chars:", len(token))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
