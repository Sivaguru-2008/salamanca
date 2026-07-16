"""UTC-first date/time helpers.

All persistence and business logic operate on timezone-aware UTC datetimes.
SQLite (used in tests) returns naive datetimes, so comparisons against
database values must go through :func:`ensure_utc`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Attach UTC to naive datetimes; convert aware datetimes to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_isoformat(value: datetime) -> str:
    return ensure_utc(value).isoformat().replace("+00:00", "Z")


def from_isoformat(value: str) -> datetime:
    return ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def start_of_day(value: datetime) -> datetime:
    aware = ensure_utc(value)
    return aware.replace(hour=0, minute=0, second=0, microsecond=0)


def days_ago(days: int, *, reference: datetime | None = None) -> datetime:
    base = ensure_utc(reference) if reference else utc_now()
    return base - timedelta(days=days)


def is_expired(expires_at: datetime, *, reference: datetime | None = None) -> bool:
    base = ensure_utc(reference) if reference else utc_now()
    return ensure_utc(expires_at) <= base
