"""Cursor pagination: opaque base64 cursors over a stable offset window."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.errors import ValidationAppError

T = TypeVar("T")

MAX_PAGE_LIMIT = 100
DEFAULT_PAGE_LIMIT = 20


def encode_cursor(offset: int) -> str:
    payload = json.dumps({"o": offset}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> int:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        offset = int(payload["o"])
    except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValidationAppError("Invalid pagination cursor.") from exc
    if offset < 0:
        raise ValidationAppError("Invalid pagination cursor.")
    return offset


class PageParams(BaseModel):
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    offset: int = Field(default=0, ge=0)

    @classmethod
    def from_query(cls, *, limit: int, cursor: str | None) -> PageParams:
        offset = decode_cursor(cursor) if cursor else 0
        return cls(limit=limit, offset=offset)


class Page(BaseModel, Generic[T]):
    """Standard paginated response envelope."""

    items: list[T]
    total: int
    limit: int
    next_cursor: str | None = None

    @classmethod
    def build(cls, items: list[T], total: int, params: PageParams) -> Page[T]:
        next_offset = params.offset + params.limit
        return cls(
            items=items,
            total=total,
            limit=params.limit,
            next_cursor=encode_cursor(next_offset) if next_offset < total else None,
        )
