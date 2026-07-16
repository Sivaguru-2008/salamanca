"""In-process background task framework.

Supports fire-and-forget tasks and supervised periodic tasks. Periodic tasks
survive handler exceptions (logged + counted), respect cancellation, and are
drained on shutdown as part of the application lifecycle.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any

import structlog

from app.core.metrics import BACKGROUND_TASK_RUNS_TOTAL

logger = structlog.get_logger(__name__)

AsyncTaskFn = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class PeriodicSpec:
    name: str
    interval_seconds: float
    fn: AsyncTaskFn
    jitter_seconds: float = 0.0
    run_immediately: bool = False


class BackgroundTaskManager:
    def __init__(self) -> None:
        self._periodic: list[PeriodicSpec] = []
        self._tasks: set[asyncio.Task[Any]] = set()
        self._started = False

    def add_periodic(
        self,
        name: str,
        interval_seconds: float,
        fn: AsyncTaskFn,
        *,
        jitter_seconds: float = 0.0,
        run_immediately: bool = False,
    ) -> None:
        if self._started:
            raise RuntimeError("cannot register periodic tasks after start()")
        self._periodic.append(
            PeriodicSpec(
                name=name,
                interval_seconds=interval_seconds,
                fn=fn,
                jitter_seconds=jitter_seconds,
                run_immediately=run_immediately,
            )
        )

    def spawn(self, coro: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task[Any]:
        """Track a fire-and-forget task; exceptions are logged, never lost."""
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._on_task_done)
        return task

    def _on_task_done(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("background_task_error", task=task.get_name(), error=str(exc))
            BACKGROUND_TASK_RUNS_TOTAL.labels(task=task.get_name(), outcome="error").inc()
        else:
            BACKGROUND_TASK_RUNS_TOTAL.labels(task=task.get_name(), outcome="success").inc()

    async def _run_periodic(self, spec: PeriodicSpec) -> None:
        if not spec.run_immediately:
            await asyncio.sleep(self._next_delay(spec))
        while True:
            try:
                await spec.fn()
                BACKGROUND_TASK_RUNS_TOTAL.labels(task=spec.name, outcome="success").inc()
            except asyncio.CancelledError:
                raise
            except Exception:
                BACKGROUND_TASK_RUNS_TOTAL.labels(task=spec.name, outcome="error").inc()
                logger.exception("periodic_task_failed", task=spec.name)
            await asyncio.sleep(self._next_delay(spec))

    @staticmethod
    def _next_delay(spec: PeriodicSpec) -> float:
        jitter = random.uniform(0, spec.jitter_seconds) if spec.jitter_seconds > 0 else 0.0
        return spec.interval_seconds + jitter

    async def start(self) -> None:
        self._started = True
        for spec in self._periodic:
            task = asyncio.create_task(self._run_periodic(spec), name=f"periodic:{spec.name}")
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        if self._periodic:
            logger.info("background_tasks_started", count=len(self._periodic))

    async def stop(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks.clear()
        logger.info("background_tasks_stopped")
