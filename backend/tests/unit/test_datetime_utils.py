from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from app.utils.datetime import (
    days_ago,
    ensure_utc,
    from_isoformat,
    is_expired,
    start_of_day,
    to_isoformat,
    utc_now,
)


def test_utc_now_is_aware() -> None:
    now = utc_now()
    assert now.tzinfo is UTC


def test_ensure_utc_attaches_to_naive() -> None:
    naive = datetime(2026, 7, 16, 12, 0, 0)
    aware = ensure_utc(naive)
    assert aware.tzinfo is UTC
    assert aware.hour == 12


def test_ensure_utc_converts_other_zones() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    value = datetime(2026, 7, 16, 17, 30, tzinfo=ist)
    assert ensure_utc(value).hour == 12


def test_isoformat_roundtrip() -> None:
    now = utc_now().replace(microsecond=0)
    assert from_isoformat(to_isoformat(now)) == now
    assert to_isoformat(now).endswith("Z")


def test_start_of_day() -> None:
    value = start_of_day(datetime(2026, 7, 16, 18, 45, 12, tzinfo=UTC))
    assert (value.hour, value.minute, value.second) == (0, 0, 0)


def test_days_ago() -> None:
    reference = datetime(2026, 7, 16, tzinfo=UTC)
    assert days_ago(7, reference=reference) == reference - timedelta(days=7)


def test_is_expired_handles_naive_database_values() -> None:
    past_naive = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
    future = utc_now() + timedelta(hours=1)
    assert is_expired(past_naive)
    assert not is_expired(future)
