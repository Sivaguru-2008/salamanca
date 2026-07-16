"""Seed framework: registered, ordered, idempotent seeders.

Every seeder must be safe to run repeatedly — it reports ``created`` or
``skipped`` instead of failing when data already exists.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import ClassVar, TypeVar

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import NotFoundError

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class SeedResult:
    seeder: str
    outcome: str
    detail: str = ""


class Seeder(abc.ABC):
    """A named, idempotent seed unit. Lower ``order`` runs first."""

    name: ClassVar[str]
    order: ClassVar[int] = 100

    @abc.abstractmethod
    async def run(self, session: AsyncSession, settings: Settings) -> SeedResult:
        raise NotImplementedError


_REGISTRY: dict[str, type[Seeder]] = {}

SeederT = TypeVar("SeederT", bound=type[Seeder])


def register_seeder(cls: SeederT) -> SeederT:
    _REGISTRY[cls.name] = cls
    return cls


def registered_seeders() -> list[type[Seeder]]:
    return sorted(_REGISTRY.values(), key=lambda c: (c.order, c.name))


async def run_seeders(
    session: AsyncSession,
    settings: Settings,
    *,
    only: list[str] | None = None,
) -> list[SeedResult]:
    selected = registered_seeders()
    if only:
        unknown = set(only) - set(_REGISTRY)
        if unknown:
            raise NotFoundError(f"Unknown seeder(s): {', '.join(sorted(unknown))}")
        selected = [cls for cls in selected if cls.name in set(only)]

    results: list[SeedResult] = []
    for cls in selected:
        result = await cls().run(session, settings)
        logger.info("seeder_finished", seeder=result.seeder, outcome=result.outcome)
        results.append(result)
    return results
