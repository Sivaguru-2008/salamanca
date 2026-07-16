"""In-process Redis stand-in used when no Redis server is reachable.

Implements only the commands the application actually issues (rate limiting
counters and council chat history lists). Data lives in the worker process and
is lost on restart — acceptable for local development, never for production.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any


class MemoryRedis:
    """Async, TTL-aware subset of the redis-py client API."""

    def __init__(self) -> None:
        self._values: dict[str, int] = {}
        self._lists: dict[str, list[str]] = {}
        self._expiries: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _purge(self, key: str) -> None:
        deadline = self._expiries.get(key)
        if deadline is not None and deadline <= time.monotonic():
            self._values.pop(key, None)
            self._lists.pop(key, None)
            self._expiries.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    async def incr(self, key: str) -> int:
        async with self._lock:
            self._purge(key)
            self._values[key] = self._values.get(key, 0) + 1
            return self._values[key]

    async def ttl(self, key: str) -> int:
        async with self._lock:
            self._purge(key)
            if key not in self._values and key not in self._lists:
                return -2
            deadline = self._expiries.get(key)
            if deadline is None:
                return -1
            return max(0, int(deadline - time.monotonic()))

    async def expire(self, key: str, seconds: int) -> bool:
        async with self._lock:
            self._purge(key)
            if key not in self._values and key not in self._lists:
                return False
            self._expiries[key] = time.monotonic() + seconds
            return True

    async def rpush(self, key: str, *values: Any) -> int:
        async with self._lock:
            self._purge(key)
            entries = self._lists.setdefault(key, [])
            entries.extend(str(v) for v in values)
            return len(entries)

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        async with self._lock:
            self._purge(key)
            entries = self._lists.get(key, [])
            stop = len(entries) if end == -1 else end + 1
            return entries[start:stop]

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        async with self._lock:
            self._purge(key)
            entries = self._lists.get(key, [])
            stop = len(entries) if end == -1 else end + 1
            self._lists[key] = entries[start:stop]
            return True
