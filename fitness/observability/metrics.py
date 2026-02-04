from __future__ import annotations

import time
from collections.abc import Callable

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNTER = Counter(
    "fitness_request_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "fitness_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)
DEPLOY_TIMESTAMP = Gauge(
    "app_deploy_timestamp_seconds",
    "Unix timestamp of current deployment (set on startup)",
)

# Initialize deploy timestamp on module load
DEPLOY_TIMESTAMP.set_to_current_time()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect Prometheus metrics for each request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        route = request.scope.get("route")
        path_template = getattr(route, "path", request.url.path)
        REQUEST_COUNTER.labels(
            request.method, path_template, response.status_code
        ).inc()
        REQUEST_LATENCY.labels(request.method, path_template).observe(duration)
        return response


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
