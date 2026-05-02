#!/usr/bin/env python3
"""Write a minimal valid WAV under public/fixtures for LiveKit fallback until Dev D replaces it."""

import math
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_WEB = ROOT / "frontend" / "public" / "fixtures" / "attacker.wav"
OUT_FIXTURES = ROOT / "fixtures" / "attacker.wav"


def write_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    duration_sec = 0.9
    sample_rate = 16_000
    n = int(sample_rate * duration_sec)
    # Audible demo tone (~880 Hz) at ~35% of int16 range — old file used ±120 (inaudible).
    amp = 10_000
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        for i in range(n):
            t = i / sample_rate
            v = int(amp * math.sin(2 * math.pi * 880.0 * t))
            v = max(-32_767, min(32_767, v))
            w.writeframes(int(v).to_bytes(2, "little", signed=True))


def main() -> None:
    write_wav(OUT_WEB)
    write_wav(OUT_FIXTURES)
    print("Wrote", OUT_WEB, "and", OUT_FIXTURES)


if __name__ == "__main__":
    main()
