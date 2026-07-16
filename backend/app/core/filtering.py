"""Query-string filtering and sorting specs.

Filters use ``field:op:value`` (value may itself contain ``:``); sorts use a
comma-separated field list with a ``-`` prefix for descending order. Fields
are validated against a per-endpoint allowlist; SQL translation lives in the
repository layer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.core.errors import ValidationAppError


class FilterOperator(StrEnum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    LIKE = "like"
    ILIKE = "ilike"
    IN = "in"


@dataclass(frozen=True, slots=True)
class FieldFilter:
    field: str
    operator: FilterOperator
    value: str


@dataclass(frozen=True, slots=True)
class SortField:
    field: str
    descending: bool


def parse_filters(raw: Sequence[str], allowed_fields: frozenset[str]) -> list[FieldFilter]:
    filters: list[FieldFilter] = []
    for item in raw:
        parts = item.split(":", 2)
        if len(parts) != 3:
            raise ValidationAppError(f"Invalid filter '{item}'. Expected format 'field:op:value'.")
        field, op_raw, value = parts
        if field not in allowed_fields:
            raise ValidationAppError(
                f"Filtering by '{field}' is not supported. "
                f"Allowed: {', '.join(sorted(allowed_fields))}."
            )
        try:
            operator = FilterOperator(op_raw)
        except ValueError as exc:
            raise ValidationAppError(
                f"Unknown filter operator '{op_raw}'. "
                f"Allowed: {', '.join(op.value for op in FilterOperator)}."
            ) from exc
        filters.append(FieldFilter(field=field, operator=operator, value=value))
    return filters


def parse_sort(
    raw: str | None,
    allowed_fields: frozenset[str],
    *,
    default: str = "-created_at",
) -> list[SortField]:
    spec = raw if raw and raw.strip() else default
    sort_fields: list[SortField] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        descending = token.startswith("-")
        field = token.lstrip("+-")
        if field not in allowed_fields:
            raise ValidationAppError(
                f"Sorting by '{field}' is not supported. "
                f"Allowed: {', '.join(sorted(allowed_fields))}."
            )
        sort_fields.append(SortField(field=field, descending=descending))
    if not sort_fields:
        raise ValidationAppError("Sort specification is empty.")
    return sort_fields
