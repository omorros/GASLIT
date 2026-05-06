from __future__ import annotations

import pytest

from gaslit.agents import sentinel


@pytest.fixture(autouse=True)
def _reset_stop_event():
    sentinel._stop_event.clear()
    yield
    sentinel._stop_event.clear()


class _TimedOutThread:
    def __init__(self) -> None:
        self.join_called_with: float | None = None

    def is_alive(self) -> bool:
        return True

    def join(self, timeout: float | None = None) -> None:
        self.join_called_with = timeout


def test_stop_local_timeout_keeps_worker_stopping(monkeypatch) -> None:
    updates: list[tuple[str, str, str]] = []
    worker = _TimedOutThread()

    monkeypatch.setattr(sentinel, "_worker_thread", worker)
    monkeypatch.setattr(sentinel, "_run_id", "run-old")
    monkeypatch.setattr(sentinel, "_db", lambda: object())
    monkeypatch.setattr(sentinel, "_last_superstep", lambda _db: 42)
    monkeypatch.setattr(
        sentinel,
        "_register_agent_status",
        lambda _db, status, run_id, note="", superstep=None: updates.append(
            (status, run_id, note)
        ),
    )
    sentinel._stop_event.clear()

    stopped = sentinel.stop_local(timeout_s=0.01)
    started = sentinel.start_local()

    assert worker.join_called_with == 0.01
    assert stopped["status"] == "stopping"
    assert started["status"] == "stopping"
    assert started["run_id"] == "run-old"
    assert sentinel._worker_thread is worker
    assert sentinel._stop_event.is_set()
    assert updates == [("stopping", "run-old", "Sentinel stopping (local)")]
