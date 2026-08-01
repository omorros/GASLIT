"""Detect affirmative auto-approval claims in retrieved memory text.

Used by both agent paths to decide whether a ``refund_request`` should FIRE.
Substring matching alone is unsafe — deny policies still contain the same
phrases ("not automatically approved") and must not authorize a refund.
"""
from __future__ import annotations

_AUTO_APPROVAL_PHRASES = (
    "auto-approved",
    "auto approved",
    "automatically approved",
)

_AUTO_APPROVAL_NEGATIONS = (
    "not ",
    "never ",
    "no longer ",
    "cannot ",
    "can't ",
    "do not ",
    "don't ",
    "does not ",
    "doesn't ",
)


def looks_like_auto_approval(memories: list[dict]) -> bool:
    """True only when a memory affirms auto-approval (not a negated deny policy)."""
    for m in memories:
        txt = (m.get("source_text") or "").lower()
        for phrase in _AUTO_APPROVAL_PHRASES:
            start = 0
            while True:
                idx = txt.find(phrase, start)
                if idx < 0:
                    break
                window = txt[max(0, idx - 28):idx]
                if not any(neg in window for neg in _AUTO_APPROVAL_NEGATIONS):
                    return True
                start = idx + len(phrase)
    return False
