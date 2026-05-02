"""Nemotron 3 Super client for Sentinel drift explanations (Teammate 1).

The Sentinel only spends a model call when ``drift_score > DRIFT_THRESHOLD``
(0.62). For every crossing event this module returns a short, plain-text
explanation that the Forensic Auditor stitches into the dossier.

Design notes
------------

* OpenAI-compatible endpoint at https://integrate.api.nvidia.com/v1.
* Model: ``nvidia/nemotron-3-super-120b-a12b`` (override via ``NEMOTRON_MODEL``).
* TTL LRU cache on ``(memory_id, drift_bucket)`` — 5 min, 256 entries.
  Avoids hammering the NVIDIA endpoint when the Change Stream fires the
  same drift crossing repeatedly.
* Rate guard: 40 RPM rolling window. If exceeded, skip Nemotron.
* Fallback: on ``RateLimitError`` / connection errors, retry once with
  Anthropic ``claude-haiku-4-5-20251001`` so the dossier still gets text
  and the demo stays alive.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("gaslit.sentinel.nemotron")


# ─── Config / constants ──────────────────────────────────────────────
NEMOTRON_BASE_URL_DEFAULT = "https://integrate.api.nvidia.com/v1"
NEMOTRON_MODEL_DEFAULT = "nvidia/nemotron-3-super-120b-a12b"
ANTHROPIC_FALLBACK_DEFAULT = "claude-haiku-4-5-20251001"

CACHE_TTL_SECONDS = 300          # 5-min TTL per PRD §6
CACHE_MAX_ENTRIES = 256
RATE_LIMIT_WINDOW_S = 60         # rolling 60s window
RATE_LIMIT_MAX_CALLS = 40        # keep under Nemotron free-tier RPM

# Nemotron 3 Super is a reasoning model. By default it emits a
# chain-of-thought preamble. "detailed thinking off" (first line of the
# system prompt) is the documented switch to suppress that reasoning trace
# and return only the final answer — see build.nvidia.com Nemotron docs.
SYSTEM_PROMPT = (
    "detailed thinking off\n"
    "You are the GASLIT Sentinel, a belief-layer drift detector. Given a "
    "suspicious memory and its drift metrics, write exactly 2 to 3 short "
    "sentences explaining why the memory is anomalous and what attack "
    "pattern it most resembles (MINJA bridging-steps, indirect injection, "
    "or exfiltration). Cite the drift score and cohort variance. Do not "
    "speculate beyond the evidence. Output only the final explanation as "
    "plain prose — no preamble, no scratch notes, no bullet points, no "
    "markdown."
)


# ─── TTL LRU cache ───────────────────────────────────────────────────
@dataclass
class _Entry:
    value: str
    expires_at: float


class _TTLCache:
    """Thread-safe LRU with per-entry TTL."""

    def __init__(self, max_entries: int, ttl_seconds: float) -> None:
        self._max = max_entries
        self._ttl = ttl_seconds
        self._data: "OrderedDict[tuple, _Entry]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: tuple) -> Optional[str]:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry.expires_at < time.time():
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return entry.value

    def set(self, key: tuple, value: str) -> None:
        with self._lock:
            self._data[key] = _Entry(value=value, expires_at=time.time() + self._ttl)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


_cache = _TTLCache(CACHE_MAX_ENTRIES, CACHE_TTL_SECONDS)
_rate_window: deque[float] = deque()
_rate_lock = threading.Lock()


def _rate_ok() -> bool:
    now = time.time()
    with _rate_lock:
        while _rate_window and _rate_window[0] < now - RATE_LIMIT_WINDOW_S:
            _rate_window.popleft()
        if len(_rate_window) >= RATE_LIMIT_MAX_CALLS:
            return False
        _rate_window.append(now)
        return True


# ─── Clients ─────────────────────────────────────────────────────────
_nemotron_client = None
_nemotron_client_lock = threading.Lock()
_anthropic_client = None
_anthropic_client_lock = threading.Lock()


def _get_nemotron_client():
    global _nemotron_client
    with _nemotron_client_lock:
        if _nemotron_client is None:
            from openai import OpenAI

            api_key = os.environ.get("NVIDIA_API_KEY")
            if not api_key:
                raise RuntimeError("NVIDIA_API_KEY missing; cannot create Nemotron client")
            _nemotron_client = OpenAI(
                base_url=os.environ.get("NEMOTRON_BASE_URL", NEMOTRON_BASE_URL_DEFAULT),
                api_key=api_key,
            )
    return _nemotron_client


def _get_anthropic_client():
    global _anthropic_client
    with _anthropic_client_lock:
        if _anthropic_client is None:
            from anthropic import Anthropic

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY missing; no Nemotron fallback")
            _anthropic_client = Anthropic(api_key=api_key)
    return _anthropic_client


# ─── Public API ──────────────────────────────────────────────────────
def _prompt(memory_id: str, drift_score: float, cohort_variance: float,
            snippet: str, retrieval_count: int) -> str:
    return (
        f"memory_id: {memory_id}\n"
        f"drift_score: {drift_score:.3f} (threshold 0.62)\n"
        f"cohort_variance_ratio: {cohort_variance:.2f}x baseline\n"
        f"retrieval_count: {retrieval_count}\n"
        f"snippet: {snippet!r}\n\n"
        "Explain in 2–3 sentences what attack pattern this most resembles "
        "and why it crossed the drift threshold."
    )


_SCRATCH_PAD_MARKERS = (
    "we need to", "we should", "we must", "let's craft", "let me ",
    "let's ", "provide 2-3", "provide answer", "provide a ",
    "the user wants", "the user asks", "the user is ",
    "okay,", "alright,", "so we ", "so answer:",
    "first, ", "now, ", "need to respond",
)


def _looks_like_scratch_pad(text: str) -> bool:
    """Return True if the text still looks like a reasoning trace after extraction."""
    if not text:
        return True
    lower = text.lower()
    for marker in _SCRATCH_PAD_MARKERS:
        if lower.startswith(marker):
            return True
    for marker in ("let's craft", "provide answer", "so answer:", "need to output"):
        if marker in lower:
            return True
    return False


def _finalize_nemotron_content(raw: str) -> str:
    """Prefer the last substantial paragraph — Nemotron often prefixes chain-of-thought."""
    text = _strip_think_tags((raw or "").strip())
    if not text:
        return text
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(parts) >= 2:
        tail = parts[-1]
        if len(tail) >= 35:
            return tail
        body = "\n\n".join(parts[1:]).strip()
        if len(body) >= 35:
            return body
    return text


def _strip_think_tags(text: str) -> str:
    """Some Nemotron variants emit ``<think>...</think>`` blocks inside the
    content channel. ``detailed thinking off`` usually routes the reasoning
    into the separate ``reasoning_content`` attribute, but strip the tags
    defensively in case.
    """
    if not text:
        return text
    import re

    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


def _call_nemotron(user_prompt: str, *, max_tokens: int = 260) -> str:
    client = _get_nemotron_client()
    model = os.environ.get("NEMOTRON_MODEL", NEMOTRON_MODEL_DEFAULT)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=max_tokens,
        timeout=20.0,
    )
    msg = resp.choices[0].message
    raw = (getattr(msg, "content", None) or "").strip()
    text = _finalize_nemotron_content(raw)
    if _looks_like_scratch_pad(text):
        raise RuntimeError("nemotron emitted reasoning trace instead of final answer")
    return text


def _call_anthropic_fallback(user_prompt: str) -> str:
    client = _get_anthropic_client()
    model = os.environ.get("ANTHROPIC_FALLBACK_MODEL", ANTHROPIC_FALLBACK_DEFAULT)
    resp = client.messages.create(
        model=model,
        system=SYSTEM_PROMPT,
        max_tokens=220,
        messages=[{"role": "user", "content": user_prompt}],
    )
    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    return ("".join(parts)).strip()


def explain_drift(
    memory_id: str,
    drift_score: float,
    cohort_variance: float,
    snippet: str,
    retrieval_count: int = 0,
) -> str:
    """Return a 2–3 sentence explanation of why ``memory_id`` tripped the Sentinel.

    Cached per ``(memory_id, drift_bucket)`` where bucket is drift rounded to 0.1.
    Falls back to Anthropic Haiku on rate-limit / error so the dossier always
    has text.
    """
    drift_bucket = round(drift_score, 1)
    cache_key = (memory_id, drift_bucket)

    cached = _cache.get(cache_key)
    if cached:
        return cached

    user_prompt = _prompt(memory_id, drift_score, cohort_variance, snippet, retrieval_count)

    _want_anthropic_fb = os.environ.get(
        "SENTINEL_ANTHROPIC_FALLBACK", "1",
    ).strip().lower() not in ("0", "false", "no", "off")

    if _rate_ok():
        try:
            text = _call_nemotron(user_prompt)
            if text:
                _cache.set(cache_key, text)
                return text
            log.warning("nemotron returned empty response; falling back to anthropic")
        except Exception as exc:
            log.warning("nemotron call failed (%s); retrying with larger budget",
                        type(exc).__name__)
            try:
                text = _call_nemotron(user_prompt, max_tokens=420)
                if text:
                    _cache.set(cache_key, text)
                    return text
            except Exception as exc2:
                log.warning("nemotron retry failed (%s); falling back to anthropic",
                            type(exc2).__name__)
    else:
        log.warning("nemotron rate budget exhausted; using anthropic fallback")

    if _want_anthropic_fb:
        try:
            text = _call_anthropic_fallback(user_prompt)
            if text:
                _cache.set(cache_key, text)
                return text
        except Exception as exc:
            log.warning("anthropic fallback failed (%s); returning stub explanation",
                        type(exc).__name__)

    stub = (
        f"Drift score {drift_score:.2f} exceeds threshold 0.62 for {memory_id}. "
        f"Cohort variance is {cohort_variance:.2f}x baseline — "
        f"the memory is being retrieved by semantically unrelated queries, "
        "consistent with MINJA bridging-steps. Full explanation unavailable "
        + ("(Nemotron unreachable; Anthropic fallback disabled or failed)."
           if not _want_anthropic_fb else "(Nemotron + Anthropic both unreachable).")
    )
    _cache.set(cache_key, stub)
    return stub


def cache_stats() -> dict:
    """Lightweight introspection for debug endpoints / tests."""
    with _rate_lock:
        recent_calls = len(_rate_window)
    return {
        "cache_size": len(_cache),
        "cache_max": CACHE_MAX_ENTRIES,
        "cache_ttl_s": CACHE_TTL_SECONDS,
        "recent_calls_60s": recent_calls,
        "rate_limit_rpm": RATE_LIMIT_MAX_CALLS,
    }


__all__ = ["explain_drift", "cache_stats"]
