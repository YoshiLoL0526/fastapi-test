from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.requests import Request

from load_tester.core.config import settings
from load_tester.core.metrics import TestStatus, metrics_store

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Active test task — one at a time
_test_task: asyncio.Task | None = None

VALID_SCENARIOS = ["combined", "ramp_up", "spike", "sustained"]


class DashboardConfigPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_base_url: str | None = None
    max_workers: int | None = Field(default=None, ge=1, le=5000)
    token_pool_size: int | None = Field(default=None, ge=1, le=5000)
    think_time_min_ms: int | None = Field(default=None, ge=0, le=60_000)
    think_time_max_ms: int | None = Field(default=None, ge=0, le=60_000)
    request_timeout_s: float | None = Field(default=None, gt=0, le=300)
    ramp_initial_workers: int | None = Field(default=None, ge=1, le=5000)
    ramp_step_workers: int | None = Field(default=None, ge=1, le=5000)
    ramp_step_interval_s: float | None = Field(default=None, gt=0, le=3600)
    spike_base_workers: int | None = Field(default=None, ge=1, le=5000)
    spike_peak_workers: int | None = Field(default=None, ge=1, le=5000)
    spike_base_before_s: float | None = Field(default=None, ge=0, le=3600)
    spike_peak_duration_s: float | None = Field(default=None, gt=0, le=3600)
    spike_base_after_s: float | None = Field(default=None, ge=0, le=3600)
    sustained_workers: int | None = Field(default=None, ge=1, le=5000)
    sustained_duration_s: float | None = Field(default=None, gt=0, le=86_400)

    @model_validator(mode="after")
    def validate_ranges(self) -> "DashboardConfigPayload":
        if (
            self.think_time_min_ms is not None
            and self.think_time_max_ms is not None
            and self.think_time_min_ms > self.think_time_max_ms
        ):
            raise ValueError("think_time_min_ms cannot be greater than think_time_max_ms")
        return self


class StartRequest(DashboardConfigPayload):
    scenario: str = "combined"


def _config_snapshot() -> dict[str, object]:
    return {
        "api_base_url": settings.api_base_url,
        "default_scenario": settings.scenario,
        "max_workers": settings.max_workers,
        "token_pool_size": settings.token_pool_size,
        "think_time_min_ms": settings.think_time_min_ms,
        "think_time_max_ms": settings.think_time_max_ms,
        "request_timeout_s": settings.request_timeout_s,
        "ramp_initial_workers": settings.ramp_initial_workers,
        "ramp_step_workers": settings.ramp_step_workers,
        "ramp_step_interval_s": settings.ramp_step_interval_s,
        "spike_base_workers": settings.spike_base_workers,
        "spike_peak_workers": settings.spike_peak_workers,
        "spike_base_before_s": settings.spike_base_before_s,
        "spike_peak_duration_s": settings.spike_peak_duration_s,
        "spike_base_after_s": settings.spike_base_after_s,
        "sustained_workers": settings.sustained_workers,
        "sustained_duration_s": settings.sustained_duration_s,
        "scenarios": VALID_SCENARIOS,
    }


def _apply_runtime_config(payload: DashboardConfigPayload) -> None:
    updates = payload.model_dump(exclude_none=True)
    max_workers = updates.get("max_workers", settings.max_workers)
    sustained_workers = updates.get("sustained_workers", settings.sustained_workers)
    ramp_initial_workers = updates.get("ramp_initial_workers", settings.ramp_initial_workers)
    spike_base_workers = updates.get("spike_base_workers", settings.spike_base_workers)
    spike_peak_workers = updates.get("spike_peak_workers", settings.spike_peak_workers)

    if sustained_workers > max_workers:
        raise ValueError("sustained_workers cannot exceed max_workers")
    if ramp_initial_workers > max_workers:
        raise ValueError("ramp_initial_workers cannot exceed max_workers")
    if spike_base_workers > max_workers:
        raise ValueError("spike_base_workers cannot exceed max_workers")
    if spike_peak_workers > max_workers:
        raise ValueError("spike_peak_workers cannot exceed max_workers")

    for field, value in updates.items():
        setattr(settings, field, value)


def create_app() -> FastAPI:
    app = FastAPI(title="Load Tester Dashboard", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # ── Pages ──────────────────────────────────────────────────────────────────

    @app.get("/", include_in_schema=False)
    async def index(request: Request):
        return templates.TemplateResponse(request, "index.html")

    # ── Test control ───────────────────────────────────────────────────────────

    @app.post("/start")
    async def start_test(body: StartRequest):
        global _test_task
        if metrics_store.status == TestStatus.running:
            return JSONResponse({"error": "A test is already running"}, status_code=409)
        if body.scenario not in VALID_SCENARIOS:
            return JSONResponse(
                {"error": f"Unknown scenario '{body.scenario}'. Valid: {VALID_SCENARIOS}"},
                status_code=422,
            )
        try:
            _apply_runtime_config(body)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)

        settings.scenario = body.scenario
        from load_tester.runner import run_test
        _test_task = asyncio.create_task(run_test(body.scenario))
        return {"status": "started", "scenario": body.scenario, "config": _config_snapshot()}

    @app.post("/stop")
    async def stop_test():
        global _test_task
        if _test_task and not _test_task.done():
            _test_task.cancel()
            return {"status": "stopped"}
        return {"status": "not_running"}

    @app.get("/config")
    async def get_config():
        return _config_snapshot()

    @app.put("/config")
    async def update_config(body: DashboardConfigPayload):
        if metrics_store.status == TestStatus.running:
            return JSONResponse({"error": "Cannot change config while a test is running"}, status_code=409)
        try:
            _apply_runtime_config(body)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        return {"status": "updated", "config": _config_snapshot()}

    # ── Streaming & data ───────────────────────────────────────────────────────

    @app.get("/stream")
    async def sse_stream() -> StreamingResponse:
        return StreamingResponse(_event_generator(), media_type="text/event-stream")

    @app.get("/report")
    async def download_report(format: str = "json") -> Response:
        if metrics_store.status not in (TestStatus.finished,):
            return JSONResponse({"error": "Test not finished yet"}, status_code=409)

        report = metrics_store.build_report()

        if format == "csv":
            lines = ["elapsed_s,workers_active,rps,p50,p95,p99,error_rate_pct,throughput_kbps,total_requests,total_errors"]
            for snap in metrics_store._snapshots:
                lines.append(
                    f"{snap.elapsed_s:.1f},{snap.workers_active},{snap.rps},"
                    f"{snap.p50},{snap.p95},{snap.p99},"
                    f"{snap.error_rate_pct},{snap.throughput_kbps},"
                    f"{snap.total_requests},{snap.total_errors}"
                )
            content = "\n".join(lines)
            ts = int(metrics_store.finished_at or time.time())
            return Response(
                content=content,
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="report_{ts}.csv"'},
            )

        ts = int(metrics_store.finished_at or time.time())
        return Response(
            content=json.dumps(report, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="report_{ts}.json"'},
        )

    @app.get("/api/errors")
    async def recent_errors():
        errors = metrics_store.recent_errors()
        return [
            {
                "ts": e.ts,
                "endpoint": e.endpoint,
                "status_code": e.status_code,
                "error_kind": e.error_kind,
                "worker_id": e.worker_id,
                "message": e.message[:100],
            }
            for e in reversed(errors[-20:])
        ]

    @app.get("/api/endpoints")
    async def endpoint_table():
        return metrics_store.endpoint_table()

    return app


async def _event_generator() -> AsyncIterator[str]:
    while True:
        snap = metrics_store.snapshot()
        payload = {
            "ts": snap.ts,
            "elapsed_s": snap.elapsed_s,
            "workers_active": snap.workers_active,
            "rps": snap.rps,
            "error_rate_pct": snap.error_rate_pct,
            "throughput_kbps": snap.throughput_kbps,
            "latency": {
                "p50": snap.p50,
                "p95": snap.p95,
                "p99": snap.p99,
            },
            "total_requests": snap.total_requests,
            "total_errors": snap.total_errors,
            "status": metrics_store.status.value,
            "scenario": metrics_store.scenario_name,
        }
        yield f"data: {json.dumps(payload)}\n\n"
        await asyncio.sleep(1.0)
