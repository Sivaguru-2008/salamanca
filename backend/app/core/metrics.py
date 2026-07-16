"""Prometheus metrics: RED (rate / errors / duration) for the HTTP edge."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "fios_http_requests_total",
    "Total HTTP requests processed.",
    labelnames=("method", "path", "status"),
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "fios_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 4.0, 10.0),
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "fios_http_requests_in_progress",
    "HTTP requests currently being processed.",
)

RATE_LIMITED_TOTAL = Counter(
    "fios_rate_limited_requests_total",
    "Requests rejected by the rate limiter.",
    labelnames=("path",),
)

BACKGROUND_TASK_RUNS_TOTAL = Counter(
    "fios_background_task_runs_total",
    "Background task executions.",
    labelnames=("task", "outcome"),
)
