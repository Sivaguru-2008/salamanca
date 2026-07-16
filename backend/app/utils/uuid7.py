"""UUID version 7 (RFC 9562) — time-ordered, non-guessable primary keys.

Layout (128 bits): 48-bit unix-millisecond timestamp | 4-bit version |
12-bit random | 2-bit variant | 62-bit random. A process-local lock plus a
monotonic sub-millisecond counter guarantees strictly increasing values even
when multiple ids are generated within the same millisecond.
"""

from __future__ import annotations

import secrets
import threading
import time
import uuid

_lock = threading.Lock()
_last_ts_ms = 0
_last_rand_a = 0


def uuid7() -> uuid.UUID:
    global _last_ts_ms, _last_rand_a

    with _lock:
        ts_ms = time.time_ns() // 1_000_000
        if ts_ms > _last_ts_ms:
            _last_ts_ms = ts_ms
            rand_a = secrets.randbits(12)
        else:
            # Same (or rewound) millisecond: bump the 12-bit counter to stay monotonic.
            ts_ms = _last_ts_ms
            rand_a = (_last_rand_a + 1) & 0xFFF
            if rand_a == 0:
                ts_ms += 1
                _last_ts_ms = ts_ms
        _last_rand_a = rand_a

    value = (ts_ms & 0xFFFF_FFFF_FFFF) << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= secrets.randbits(62)
    return uuid.UUID(int=value)


def uuid7_timestamp_ms(value: uuid.UUID) -> int:
    """Extract the unix-millisecond timestamp embedded in a UUIDv7."""
    if value.version != 7:
        raise ValueError(f"not a UUIDv7: {value}")
    return value.int >> 80


def parse_uuid(value: str) -> uuid.UUID | None:
    """Parse a string into a UUID; returns ``None`` for invalid input."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None
