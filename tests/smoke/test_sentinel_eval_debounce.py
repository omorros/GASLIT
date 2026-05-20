"""Regression checks for Sentinel burst-write evaluation coalescing."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from gaslit.agents.eval_debounce import (
    EVAL_DEBOUNCE_S,
    EVAL_MAX_DELAY_S,
    PendingEval,
    due_memory_ids,
    schedule_eval,
)


def test_burst_reschedules_until_quiet_period() -> None:
    pending: PendingEval = {}

    schedule_eval(pending, "m_4419", now=10.0)
    schedule_eval(pending, "m_4419", now=10.2)
    schedule_eval(pending, "m_4419", now=10.4)

    assert due_memory_ids(pending, now=10.89) == []
    assert due_memory_ids(pending, now=10.4 + EVAL_DEBOUNCE_S) == ["m_4419"]
    assert pending == {}


def test_continuous_events_have_max_delay_cap() -> None:
    pending: PendingEval = {}
    for step in range(10):
        schedule_eval(pending, "m_4419", now=20.0 + step * 0.3)

    assert pending["m_4419"] == (20.0, 20.0 + EVAL_MAX_DELAY_S)
    assert due_memory_ids(pending, now=21.99) == []
    assert due_memory_ids(pending, now=22.0) == ["m_4419"]


if __name__ == "__main__":
    test_burst_reschedules_until_quiet_period()
    test_continuous_events_have_max_delay_cap()
    print("sentinel_eval_debounce smoke test PASS")
