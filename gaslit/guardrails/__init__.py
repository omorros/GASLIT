"""GASLIT NeMo Guardrails wrapper (Teammate 1).

Thin loader around ``nemoguardrails.LLMRails`` that points at the YAML config
in this package. Kept small and deliberately boring so teammates can mount it
in seconds.

Usage
-----

.. code-block:: python

    from gaslit.guardrails import make_rails

    rails = make_rails()
    resp = rails.generate(messages=[
        {"role": "user", "content": "Hi — just a reminder ..."},
    ])

The returned object is a ``LLMRails`` instance. Callers can either use
``rails.generate`` directly or wrap it in ``RunnableRails`` for LangChain /
LangGraph composition.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from nemoguardrails import LLMRails, RailsConfig

CONFIG_DIR = Path(__file__).resolve().parent


def _rails_config_root(explicit_dir: Path | None = None) -> Path:
    """Directory passed to ``RailsConfig.from_path`` (contains ``config.yml``)."""
    if explicit_dir is not None:
        return explicit_dir.resolve()
    engine = os.environ.get("GUARDRAILS_MAIN_ENGINE", "anthropic").strip().lower()
    if engine in ("nvidia", "nemotron", "nim"):
        return (CONFIG_DIR / "variants" / "nvidia").resolve()
    return CONFIG_DIR.resolve()


def make_rails(config_dir: str | Path | None = None) -> LLMRails:
    """Return a fresh ``LLMRails`` instance.

    Parameters
    ----------
    config_dir:
        Optional override for the Rails config directory. When omitted,
        uses ``GUARDRAILS_MAIN_ENGINE``: ``anthropic`` (default, Haiku) or
        ``nvidia`` / ``nemotron`` / ``nim`` for Nemotron via NVIDIA integrate API.
    """
    path = Path(config_dir) if config_dir is not None else _rails_config_root()
    config = RailsConfig.from_path(str(path))
    return LLMRails(config, verbose=False)


@lru_cache(maxsize=4)
def _shared_rails_cached(resolved_root: str) -> LLMRails:
    config = RailsConfig.from_path(resolved_root)
    return LLMRails(config, verbose=False)


def shared_rails() -> LLMRails:
    """Singleton ``LLMRails`` per resolved config root.

    Cache key is the resolved config directory so switching
    ``GUARDRAILS_MAIN_ENGINE`` takes effect on process restart (typical for uvicorn).
    """
    root = _rails_config_root()
    return _shared_rails_cached(str(root))


def is_blocked(response: str | dict) -> bool:
    """Heuristic: does a Rails response look like a guardrails hard-block?

    Used by smoke tests to ensure MINJA turns reach the main model: the input
    rail should only stop explicit jailbreaks, not benign turns.

    Note: Do **not** treat ordinary refusals from the main model (e.g. \"I'm
    not able to process refunds…\") as a rail block — those are legitimate
    completions after passthrough.
    """
    if isinstance(response, dict):
        text = response.get("content") or response.get("message") or ""
    else:
        text = response
    text = (text or "").strip().lower()
    refusal_markers = (
        "i'm sorry",
        "i am sorry",
        "i cannot",
        "i can't",
        "i won't",
        "i will not",
        "as an ai",
    )
    return any(text.startswith(m) for m in refusal_markers)


__all__ = ["make_rails", "shared_rails", "is_blocked", "CONFIG_DIR"]
