"""Trailing-edge debounce for Change Stream handlers.

Leading-edge "evaluate first event, skip the rest of the window" drops the
only post-burst evaluation when later rows arrive inside the debounce window.
Trailing-edge coalescing waits for quiet, then fires once with full evidence.
"""
from __future__ import annotations

import threading
from typing import Any, Callable


class TrailingDebouncer:
    def __init__(self, delay_s: float, callback: Callable[[Any], None]) -> None:
        self._delay_s = delay_s
        self._callback = callback
        self._timers: dict[Any, threading.Timer] = {}
        self._lock = threading.Lock()

    def kick(self, key: Any) -> None:
        with self._lock:
            old = self._timers.get(key)
            if old is not None:
                old.cancel()
            timer = threading.Timer(self._delay_s, self._fire, args=(key,))
            timer.daemon = True
            self._timers[key] = timer
            timer.start()

    def _fire(self, key: Any) -> None:
        with self._lock:
            self._timers.pop(key, None)
        self._callback(key)

    def cancel_all(self) -> None:
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()

    def pending(self) -> set[Any]:
        with self._lock:
            return set(self._timers)
