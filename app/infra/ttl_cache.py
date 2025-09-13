from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from typing import Any

TTL_DEFAULT = int(os.getenv("LLM_CACHE_TTL_SECONDS", "60"))
MAX_ENTRIES = int(os.getenv("LLM_CACHE_MAX_ENTRIES", "512"))


class TTLCache:
    """Simple thread-safe TTL cache with crude LRU eviction."""

    def __init__(self, ttl_seconds: int = TTL_DEFAULT, max_entries: int = MAX_ENTRIES):
        self.ttl = ttl_seconds
        self.max = max_entries
        self._lock = threading.Lock()
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def _now(self) -> float:
        return time.time()

    def _evict_expired(self) -> None:
        now = self._now()
        # Entries are roughly in access order (we re-insert on get), but we still scan.
        dead = []
        for k, (ts, _) in self._data.items():
            if now - ts > self.ttl:
                dead.append(k)
            else:
                break
        for k in dead:
            self._data.pop(k, None)

    def _evict_lru_if_needed(self) -> None:
        while len(self._data) > self.max:
            self._data.popitem(last=False)  # evict oldest

    def get(self, key: str):
        with self._lock:
            self._evict_expired()
            if key in self._data:
                ts, val = self._data.pop(key)
                # move to end (most-recently used)
                self._data[key] = (ts, val)
                return val
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._evict_expired()
            self._data.pop(key, None)
            self._data[key] = (self._now(), value)
            self._evict_lru_if_needed()
