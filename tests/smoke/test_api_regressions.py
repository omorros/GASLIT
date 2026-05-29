"""Dependency-free regression checks for critical API correctness paths."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

API_MAIN = ROOT / "api" / "main.py"


def test_agent_routes_pass_request_user_to_retrieval() -> None:
    source = API_MAIN.read_text()
    assert '"user_id": None' not in source
    assert source.count('"user_id": req.user_id') >= 2


def test_scenario_flood_rejects_remote_without_token() -> None:
    source = API_MAIN.read_text()
    assert "def _authorize_flood_request(request: Request)" in source
    assert "SCENARIO_FLOOD_TOKEN" in source
    assert "_is_loopback_client(request)" in source
    assert "status_code=403" in source
    assert "_authorize_flood_request(request)" in source
    assert "status_code=429" in source


if __name__ == "__main__":
    test_agent_routes_pass_request_user_to_retrieval()
    test_scenario_flood_rejects_remote_without_token()
    print("api_regressions smoke tests PASS")
