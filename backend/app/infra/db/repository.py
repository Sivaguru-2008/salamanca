"""Generic async repository with filtering, sorting, and pagination."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import ColumnElement, UnaryExpression, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.errors import ValidationAppError
from app.core.filtering import FieldFilter, FilterOperator, SortField
from app.infra.db.base import Base
from app.utils.datetime import from_isoformat, utc_now

ModelT = TypeVar("ModelT", bound=Base)


def _column(model: type[Base], field: str) -> InstrumentedAttribute[Any]:
    attr = getattr(model, field, None)
    if not isinstance(attr, InstrumentedAttribute):
        raise ValidationAppError(f"Unknown field '{field}'.")
    return attr


def _coerce(column: InstrumentedAttribute[Any], value: str) -> Any:
    try:
        python_type = column.type.python_type
    except NotImplementedError:
        return value
    try:
        if python_type is bool:
            return value.strip().lower() in {"1", "true", "yes", "on"}
        if python_type is int:
            return int(value)
        if python_type is float:
            return float(value)
        if python_type is uuid.UUID:
            return uuid.UUID(value)
        if python_type is datetime:
            return from_isoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValidationAppError(f"Invalid value '{value}' for field '{column.key}'.") from exc
    return value


def build_filter_conditions(
    model: type[Base], filters: Sequence[FieldFilter]
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    for f in filters:
        column = _column(model, f.field)
        match f.operator:
            case FilterOperator.EQ:
                conditions.append(column == _coerce(column, f.value))
            case FilterOperator.NE:
                conditions.append(column != _coerce(column, f.value))
            case FilterOperator.GT:
                conditions.append(column > _coerce(column, f.value))
            case FilterOperator.GTE:
                conditions.append(column >= _coerce(column, f.value))
            case FilterOperator.LT:
                conditions.append(column < _coerce(column, f.value))
            case FilterOperator.LTE:
                conditions.append(column <= _coerce(column, f.value))
            case FilterOperator.LIKE:
                conditions.append(column.like(f"%{f.value}%"))
            case FilterOperator.ILIKE:
                conditions.append(column.ilike(f"%{f.value}%"))
            case FilterOperator.IN:
                values = [_coerce(column, v.strip()) for v in f.value.split(",") if v.strip()]
                if not values:
                    raise ValidationAppError(f"Empty 'in' filter for field '{f.field}'.")
                conditions.append(column.in_(values))
    return conditions


def build_sort_expressions(
    model: type[Base], sort_fields: Sequence[SortField]
) -> list[UnaryExpression[Any]]:
    expressions: list[UnaryExpression[Any]] = []
    for s in sort_fields:
        column = _column(model, s.field)
        expressions.append(column.desc() if s.descending else column.asc())
    return expressions


class BaseRepository(Generic[ModelT]):
    """CRUD + query building over a single aggregate root.

    Soft-deleted rows (``deleted_at`` set) are excluded from reads by default
    when the model carries the soft-delete mixin.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_select(self, *, include_deleted: bool = False) -> Any:
        stmt = select(self.model)
        if not include_deleted and hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return stmt

    async def get(self, entity_id: uuid.UUID, *, include_deleted: bool = False) -> ModelT | None:
        stmt = self._base_select(include_deleted=include_deleted).where(
            self.model.id == entity_id  # type: ignore[attr-defined]
        )
        return await self.session.scalar(stmt)

    async def get_by(self, *, include_deleted: bool = False, **criteria: Any) -> ModelT | None:
        stmt = self._base_select(include_deleted=include_deleted)
        for field, value in criteria.items():
            stmt = stmt.where(_column(self.model, field) == value)
        return await self.session.scalar(stmt)

    async def list(
        self,
        *,
        filters: Sequence[FieldFilter] | None = None,
        sort: Sequence[SortField] | None = None,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> tuple[list[ModelT], int]:
        conditions = build_filter_conditions(self.model, filters or [])
        base = self._base_select(include_deleted=include_deleted)
        if conditions:
            base = base.where(*conditions)

        total = await self.session.scalar(select(func.count()).select_from(base.subquery()))

        stmt = base
        if sort:
            stmt = stmt.order_by(*build_sort_expressions(self.model, sort))
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.scalars(stmt)
        return list(result.all()), int(total or 0)

    async def count(self, *, filters: Sequence[FieldFilter] | None = None) -> int:
        conditions = build_filter_conditions(self.model, filters or [])
        base = self._base_select()
        if conditions:
            base = base.where(*conditions)
        total = await self.session.scalar(select(func.count()).select_from(base.subquery()))
        return int(total or 0)

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def update(self, entity: ModelT, **values: Any) -> ModelT:
        for field, value in values.items():
            setattr(entity, field, value)
        await self.session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)
        await self.session.flush()

    async def soft_delete(self, entity: ModelT) -> ModelT:
        if not hasattr(entity, "deleted_at"):
            raise TypeError(f"{type(entity).__name__} does not support soft delete")
        entity.deleted_at = utc_now()  # type: ignore[attr-defined]
        await self.session.flush()
        return entity
