from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from load_tester.core.config import settings
from load_tester.core.metrics import TestStatus, metrics_store

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Active test task — one at a time
_test_task: asyncio.Task | None = None

VALID_SCENARIOS = ["combined", "ramp_up", "spike", "sustained"]


class StartRequest(BaseModel):
    scenario: str = "combined"


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
        from load_tester.runner import run_test
        _test_task = asyncio.create_task(run_test(body.scenario))
        return {"status": "started", "scenario": body.scenario}

    @app.post("/stop")
    async def stop_test():
        global _test_task
        if _test_task and not _test_task.done():
            _test_task.cancel()
            return {"status": "stopped"}
        return {"status": "not_running"}

    @app.get("/config")
    async def get_config():
        return {
            "api_base_url": settings.api_base_url,
            "default_scenario": settings.scenario,
            "max_workers": settings.max_workers,
            "scenarios": VALID_SCENARIOS,
        }

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
