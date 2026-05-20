"""Shared trailing debounce for Sentinel retrieval-log evaluation."""
from __future__ import annotations

EVAL_DEBOUNCE_S = 0.5
EVAL_MAX_DELAY_S = 2.0

PendingEval = dict[str, tuple[float, float]]


def schedule_eval(pending_eval: PendingEval, memory_id: str, now: float) -> None:
    """Coalesce bursty inserts while guaranteeing an eventual final evaluation."""
    first_seen, _ = pending_eval.get(memory_id, (now, now))
    due_at = min(now + EVAL_DEBOUNCE_S, first_seen + EVAL_MAX_DELAY_S)
    pending_eval[memory_id] = (first_seen, due_at)


def due_memory_ids(pending_eval: PendingEval, now: float) -> list[str]:
    due = [mid for mid, (_, due_at) in pending_eval.items() if due_at <= now]
    for mid in due:
        pending_eval.pop(mid, None)
    return due
