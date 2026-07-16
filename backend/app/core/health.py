"""Health-check registry backing the liveness/readiness endpoints."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

CheckFn = Callable[[], Awaitable[None]]

DEFAULT_CHECK_TIMEOUT_SECONDS = 5.0


@dataclass(slots=True)
class CheckResult:
    name: str
    healthy: bool
    latency_ms: float
    error: str | None = None
    critical: bool = True


@dataclass(slots=True)
class _RegisteredCheck:
    name: str
    fn: CheckFn
    critical: bool
    timeout: float


class HealthRegistry:
    """Named async checks; a failing *critical* check marks the app not-ready."""

    def __init__(self) -> None:
        self._checks: dict[str, _RegisteredCheck] = {}

    def register(
        self,
        name: str,
        fn: CheckFn,
        *,
        critical: bool = True,
        timeout: float = DEFAULT_CHECK_TIMEOUT_SECONDS,
    ) -> None:
        self._checks[name] = _RegisteredCheck(name=name, fn=fn, critical=critical, timeout=timeout)

    async def _run_one(self, check: _RegisteredCheck) -> CheckResult:
        start = time.perf_counter()
        try:
            await asyncio.wait_for(check.fn(), timeout=check.timeout)
        except TimeoutError:
            latency = (time.perf_counter() - start) * 1000
            return CheckResult(check.name, False, round(latency, 2), "timeout", check.critical)
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            logger.warning("health_check_failed", check=check.name, error=str(exc))
            return CheckResult(check.name, False, round(latency, 2), str(exc), check.critical)
        latency = (time.perf_counter() - start) * 1000
        return CheckResult(check.name, True, round(latency, 2), None, check.critical)

    async def run_all(self) -> tuple[bool, list[CheckResult]]:
        results = await asyncio.gather(*(self._run_one(c) for c in self._checks.values()))
        ready = all(r.healthy for r in results if r.critical)
        return ready, list(results)
