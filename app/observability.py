from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class RequestIdFilter(logging.Filter):
    """Ensure every record has a request_id attribute for JSON formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


def setup_json_logging(logger_name: str = "persona_lab") -> logging.Logger:
    """
    Configure an app logger with JSON line format:

      {"ts":"...","level":"...","msg":"...","request_id":"..."}

    Idempotent: safe to call multiple times.
    """
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    fmt = logging.Formatter(
        '{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s","request_id":"%(request_id)s"}'
    )
    handler.setFormatter(fmt)
    handler.addFilter(RequestIdFilter())

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Propagate/assign X-Request-ID and emit a compact access log per request.

    - Accepts incoming X-Request-ID or generates a UUID4.
    - Sets X-Request-ID response header.
    - Logs: method, path, status, duration_ms, client.
    """

    def __init__(self, app, logger: logging.Logger):
        super().__init__(app)
        self.log = logger

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.time()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.time() - start) * 1000)
            self.log.exception(
                'unhandled_exception method="%s" path="%s" duration_ms=%d client="%s"',
                request.method,
                request.url.path,
                duration_ms,
                request.client.host if request.client else "-",
                extra={"request_id": rid},
            )
            raise

        response.headers["X-Request-ID"] = rid

        duration_ms = int((time.time() - start) * 1000)
        self.log.info(
            'access method="%s" path="%s" status=%d duration_ms=%d client="%s"',
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request.client.host if request.client else "-",
            extra={"request_id": rid},
        )
        return response
