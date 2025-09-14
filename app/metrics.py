from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse

# Prometheus metric definitions (cardinality kept low by using path templates)
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency (seconds)",
    ["method", "path", "status"],
    # Reasonable SLO-oriented buckets; adjust later if needed
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_ERRORS_TOTAL = Counter(
    "http_errors_total",
    "Total 5xx responses",
    ["method", "path"],
)


def _path_template(request: Request) -> str:
    """
    Return the route path template (e.g., '/ready' or '/feedback').
    Falls back to the raw path if the template is unavailable.
    """
    route = request.scope.get("route")
    if route and getattr(route, "path", None):
        return route.path
    return request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Records Prometheus metrics for each request:
      - requests total (method, path, status)
      - latency histogram (method, path, status)
      - errors total (5xx)
    """

    def __init__(self, app, skip_predicate: Callable[[Request], bool] | None = None):
        super().__init__(app)
        self._skip = skip_predicate or (lambda req: False)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> StarletteResponse:
        if self._skip(request):
            return await call_next(request)

        start = time.time()
        method = request.method
        path = _path_template(request)

        try:
            response = await call_next(request)
        except Exception:
            # Count an implicit 5xx
            HTTP_ERRORS_TOTAL.labels(method=method, path=path).inc()
            # Re-raise so upstream handlers/logging still run
            raise

        status = response.status_code
        duration = time.time() - start

        # Counters & histograms
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(status)).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path, status=str(status)).observe(
            duration
        )

        if 500 <= status < 600:
            HTTP_ERRORS_TOTAL.labels(method=method, path=path).inc()

        return response


def metrics_endpoint() -> Response:
    """Return the Prometheus metrics exposition."""
    payload = generate_latest()  # bytes
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
