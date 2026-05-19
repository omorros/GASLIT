"""Regression tests for operator-only scenario flood controls."""
from __future__ import annotations

import sys
import threading
import time
import types
import unittest
from contextlib import contextmanager
from os import environ
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi.testclient import TestClient

import api.main as api_main


@contextmanager
def _operator_token(value: str | None):
    old = environ.get("GASLIT_OPERATOR_TOKEN")
    if value is None:
        environ.pop("GASLIT_OPERATOR_TOKEN", None)
    else:
        environ["GASLIT_OPERATOR_TOKEN"] = value
    try:
        yield
    finally:
        if old is None:
            environ.pop("GASLIT_OPERATOR_TOKEN", None)
        else:
            environ["GASLIT_OPERATOR_TOKEN"] = old


def _client() -> TestClient:
    api_main._FLOOD_RUNS.clear()
    return TestClient(api_main.app)


class FloodGuardTests(unittest.TestCase):
    def test_flood_disabled_without_operator_token(self) -> None:
        with _operator_token(None):
            client = _client()

            response = client.post("/api/scenario/flood", json={"duration_s": 2, "qps": 1})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(api_main._FLOOD_RUNS, {})

    def test_flood_rejects_missing_or_wrong_token(self) -> None:
        with _operator_token("secret-token"):
            client = _client()

            missing = client.post("/api/scenario/flood", json={"duration_s": 2, "qps": 1})
            wrong = client.post(
                "/api/scenario/flood",
                headers={"X-GASLIT-Operator-Token": "wrong"},
                json={"duration_s": 2, "qps": 1},
            )

        self.assertEqual(missing.status_code, 403)
        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(api_main._FLOOD_RUNS, {})

    def test_flood_allows_only_one_active_run(self) -> None:
        started = threading.Event()
        release = threading.Event()

        fake_module = types.ModuleType("gaslit.adversary.live_traffic")

        def stream_traffic(duration_s: int, qps: float, *, source: str = "canned") -> int:
            started.set()
            self.assertEqual(duration_s, 2)
            self.assertEqual(qps, 1)
            self.assertEqual(source, "canned")
            release.wait(timeout=2)
            return 3

        fake_module.stream_traffic = stream_traffic

        with _operator_token("secret-token"), patch.dict(
            sys.modules, {"gaslit.adversary.live_traffic": fake_module}
        ):
            client = _client()
            headers = {"X-GASLIT-Operator-Token": "secret-token"}
            first = client.post("/api/scenario/flood", headers=headers, json={"duration_s": 2, "qps": 1})

            self.assertEqual(first.status_code, 202)
            run_id = first.json()["run_id"]
            self.assertTrue(started.wait(timeout=1))

            second = client.post("/api/scenario/flood", headers=headers, json={"duration_s": 2, "qps": 1})
            self.assertEqual(second.status_code, 409)

            release.set()
            deadline = time.time() + 2
            status = {}
            while time.time() < deadline:
                status = client.get(f"/api/scenario/flood/{run_id}").json()
                if status.get("status") == "completed":
                    break
                time.sleep(0.02)

        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["sent"], 3)


if __name__ == "__main__":
    unittest.main()
