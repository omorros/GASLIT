"""Regression tests for operator-only scenario flood controls."""
from __future__ import annotations

import sys
import threading
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi.testclient import TestClient

import api.main as api_main


def _client() -> TestClient:
    api_main._FLOOD_RUNS.clear()
    return TestClient(api_main.app)


def test_flood_disabled_without_operator_token(monkeypatch) -> None:
    monkeypatch.delenv("GASLIT_OPERATOR_TOKEN", raising=False)
    client = _client()

    response = client.post("/api/scenario/flood", json={"duration_s": 2, "qps": 1})

    assert response.status_code == 503
    assert api_main._FLOOD_RUNS == {}


def test_flood_rejects_missing_or_wrong_token(monkeypatch) -> None:
    monkeypatch.setenv("GASLIT_OPERATOR_TOKEN", "secret-token")
    client = _client()

    missing = client.post("/api/scenario/flood", json={"duration_s": 2, "qps": 1})
    wrong = client.post(
        "/api/scenario/flood",
        headers={"X-GASLIT-Operator-Token": "wrong"},
        json={"duration_s": 2, "qps": 1},
    )

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert api_main._FLOOD_RUNS == {}


def test_flood_allows_only_one_active_run(monkeypatch) -> None:
    monkeypatch.setenv("GASLIT_OPERATOR_TOKEN", "secret-token")
    started = threading.Event()
    release = threading.Event()

    fake_module = types.ModuleType("gaslit.adversary.live_traffic")

    def stream_traffic(duration_s: int, qps: float, *, source: str = "canned") -> int:
        started.set()
        assert duration_s == 2
        assert qps == 1
        assert source == "canned"
        release.wait(timeout=2)
        return 3

    fake_module.stream_traffic = stream_traffic
    monkeypatch.setitem(sys.modules, "gaslit.adversary.live_traffic", fake_module)

    client = _client()
    headers = {"X-GASLIT-Operator-Token": "secret-token"}
    first = client.post("/api/scenario/flood", headers=headers, json={"duration_s": 2, "qps": 1})

    assert first.status_code == 202
    run_id = first.json()["run_id"]
    assert started.wait(timeout=1)

    second = client.post("/api/scenario/flood", headers=headers, json={"duration_s": 2, "qps": 1})
    assert second.status_code == 409

    release.set()
    deadline = time.time() + 2
    status = {}
    while time.time() < deadline:
        status = client.get(f"/api/scenario/flood/{run_id}").json()
        if status.get("status") == "completed":
            break
        time.sleep(0.02)

    assert status["status"] == "completed"
    assert status["sent"] == 3


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
