"""Dependency-light checks for critical operator console regressions.

These guard the client-side race fixes without requiring a browser test stack.
Run from the repo root:
  python3 tests/smoke/test_console_regressions.py
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    dossier = read("frontend/components/console/DossierPanel.tsx")
    dual = read("frontend/components/console/DualConsole.tsx")
    scenario = read("frontend/hooks/useScenarioPlayer.ts")
    page = read("frontend/app/console/page.tsx")

    require("const nextLine = queue[0];" in dossier, "TTS queue must drain by head item")
    require("}, [nextLine]);" in dossier, "TTS effect must not restart on tail enqueue")
    require("}, [queue]);" not in dossier, "TTS effect must not depend on full queue")
    require("audioEl.onended = null;" in dossier, "TTS cleanup must detach audio handlers")

    require("busyRef.current" in dual, "DualConsole send must use a synchronous busy guard")
    require("if (!message.trim() || busyRef.current) return {};" in dual, "send guard must reject overlap")
    require("runRef.current += 1;" in dual, "reset must invalidate in-flight paired dispatches")
    require("if (runId !== runRef.current) return {};" in dual, "stale dispatch results must be ignored")

    require("advancingRef.current" in scenario, "scenario advance must use a synchronous click guard")
    require("if (state.busy || advancingRef.current) return;" in scenario, "advance must reject duplicate clicks")

    require("dualHandleRef.current?.reset();" in page, "restart must reset dual-console evidence")
    require("ev.reset();" in page, "restart must reset websocket event buffers")
    require("<DossierPanel key={dossierRunKey}" in page, "restart must remount dossier state")

    print("[console-regressions] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
