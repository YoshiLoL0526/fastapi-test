import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.core.logging import get_access_logger, get_error_logger

_access = get_access_logger()
_error = get_error_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        request_id = getattr(request.state, "request_id", "-")

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            _error.exception(
                "%s %s | 500 | %.2fms | id=%s | %s",
                request.method,
                request.url.path,
                elapsed_ms,
                request_id,
                exc,
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        status = response.status_code

        _access.info(
            "%s %s | %d | %.2fms | id=%s",
            request.method,
            request.url.path,
            status,
            elapsed_ms,
            request_id,
        )

        if status >= 500:
            _error.error(
                "%s %s | %d | %.2fms | id=%s",
                request.method,
                request.url.path,
                status,
                elapsed_ms,
                request_id,
            )
        elif status >= 400:
            _error.warning(
                "%s %s | %d | %.2fms | id=%s",
                request.method,
                request.url.path,
                status,
                elapsed_ms,
                request_id,
            )

        return response
