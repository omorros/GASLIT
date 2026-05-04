from __future__ import annotations

from gaslit.adversary.local_api import local_api_base


def test_local_api_base_defaults_to_documented_api_port(monkeypatch):
    monkeypatch.delenv("API_PORT", raising=False)

    assert local_api_base() == "http://127.0.0.1:8002"


def test_local_api_base_honors_api_port_override(monkeypatch):
    monkeypatch.setenv("API_PORT", "9001")

    assert local_api_base() == "http://127.0.0.1:9001"
