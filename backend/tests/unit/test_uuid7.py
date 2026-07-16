from __future__ import annotations

import time

import pytest
from app.utils.uuid7 import parse_uuid, uuid7, uuid7_timestamp_ms


def test_version_and_variant() -> None:
    value = uuid7()
    assert value.version == 7
    assert value.variant == "specified in RFC 4122"


def test_monotonic_within_burst() -> None:
    values = [uuid7() for _ in range(1000)]
    assert values == sorted(values)
    assert len(set(values)) == 1000


def test_embedded_timestamp_is_current() -> None:
    before_ms = time.time_ns() // 1_000_000
    value = uuid7()
    after_ms = time.time_ns() // 1_000_000
    ts = uuid7_timestamp_ms(value)
    # Allow one millisecond of counter-overflow drift.
    assert before_ms - 1 <= ts <= after_ms + 1


def test_timestamp_rejects_non_v7() -> None:
    import uuid

    with pytest.raises(ValueError, match="not a UUIDv7"):
        uuid7_timestamp_ms(uuid.uuid4())


def test_parse_uuid() -> None:
    value = uuid7()
    assert parse_uuid(str(value)) == value
    assert parse_uuid("not-a-uuid") is None
