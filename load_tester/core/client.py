from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from load_tester.core.config import settings


class ErrorKind(str, Enum):
    timeout = "timeout"
    connection = "connection"
    http_4xx = "http_4xx"
    http_5xx = "http_5xx"
    ok = "ok"


@dataclass
class RequestResult:
    method: str
    endpoint: str          # normalized path (IDs replaced with {id})
    status_code: int
    latency_ms: float
    response_bytes: int
    worker_id: int
    flow_name: str
    started_at: float      # unix timestamp
    error_kind: ErrorKind = ErrorKind.ok
    error_message: str = ""

    @property
    def is_error(self) -> bool:
        return self.error_kind != ErrorKind.ok


def _normalize_path(path: str) -> str:
    """Replace UUID-like path segments with {id} for grouping."""
    import re
    uuid_pattern = re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
    )
    int_pattern = re.compile(r"/\d+(?=/|$)")
    path = uuid_pattern.sub("{id}", path)
    path = int_pattern.sub("/{id}", path)
    return path


class LoadTestClient:
    """Async HTTP client wrapper for load testing."""

    def __init__(self, worker_id: int, flow_name: str, token: str | None = None) -> None:
        self.worker_id = worker_id
        self.flow_name = flow_name
        self._token = token
        self._client: httpx.AsyncClient | None = None

    def set_token(self, token: str) -> None:
        self._token = token
        if self._client:
            self._client.headers["Authorization"] = f"Bearer {token}"

    async def __aenter__(self) -> "LoadTestClient":
        headers: dict[str, str] = {
            "User-Agent": "LoadTester/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        self._client = httpx.AsyncClient(
            base_url=settings.api_base_url,
            headers=headers,
            timeout=settings.request_timeout_s,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> tuple[RequestResult, dict[str, Any] | None]:
        assert self._client is not None, "Use inside async context manager"

        started = time.time()
        endpoint = _normalize_path(path)
        error_kind = ErrorKind.ok
        error_message = ""
        status_code = 0
        response_bytes = 0
        body: dict[str, Any] | None = None

        try:
            resp = await self._client.request(method, path, json=json, params=params)
            status_code = resp.status_code
            response_bytes = len(resp.content)
            if resp.status_code >= 500:
                error_kind = ErrorKind.http_5xx
                error_message = resp.text[:200]
            elif resp.status_code >= 400:
                error_kind = ErrorKind.http_4xx
                error_message = resp.text[:200]
            else:
                try:
                    body = resp.json()
                except Exception:
                    body = None
        except httpx.TimeoutException as exc:
            error_kind = ErrorKind.timeout
            error_message = str(exc)
        except httpx.ConnectError as exc:
            error_kind = ErrorKind.connection
            error_message = str(exc)

        latency_ms = (time.time() - started) * 1000

        result = RequestResult(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            latency_ms=latency_ms,
            response_bytes=response_bytes,
            worker_id=self.worker_id,
            flow_name=self.flow_name,
            started_at=started,
            error_kind=error_kind,
            error_message=error_message,
        )
        return result, body

    async def get(self, path: str, **kwargs: Any) -> tuple[RequestResult, dict | None]:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> tuple[RequestResult, dict | None]:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> tuple[RequestResult, dict | None]:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> tuple[RequestResult, dict | None]:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> tuple[RequestResult, dict | None]:
        return await self.request("DELETE", path, **kwargs)
