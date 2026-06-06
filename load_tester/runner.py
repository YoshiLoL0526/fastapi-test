from __future__ import annotations

import asyncio
import os
import sys
import threading
import time

import httpx

from load_tester.core.auth import token_pool
from load_tester.core.config import settings
from load_tester.core.metrics import TestStatus, metrics_store


def _check_connectivity() -> bool:
    try:
        resp = httpx.get(f"{settings.api_base_url}/health", timeout=5.0)
        return resp.status_code == 200
    except Exception as exc:
        print(f"[runner] API not reachable: {exc}")
        return False


def _start_dashboard() -> None:
    """Launch the dashboard FastAPI server in a background OS thread."""
    from load_tester.ui.main import create_app
    import uvicorn

    app = create_app()
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=settings.dashboard_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    server.run()


def _get_scenario(name: str):
    from load_tester.scenarios.ramp_up import RampUpScenario
    from load_tester.scenarios.spike import SpikeScenario
    from load_tester.scenarios.sustained import SustainedScenario
    from load_tester.scenarios.combined import CombinedScenario

    mapping = {
        "ramp_up": RampUpScenario,
        "spike": SpikeScenario,
        "sustained": SustainedScenario,
        "combined": CombinedScenario,
    }
    cls = mapping.get(name)
    if cls is None:
        print(f"[runner] Unknown scenario '{name}'. Valid options: {list(mapping)}")
        sys.exit(1)
    return cls()


async def _run_metrics_snapshot_loop(stop_event: asyncio.Event) -> None:
    """Take a snapshot every second while the test is running."""
    while not stop_event.is_set():
        if metrics_store.status == TestStatus.running:
            metrics_store.snapshot()
        await asyncio.sleep(1.0)


async def main() -> None:
    scenario_name = settings.scenario
    print(f"\n{'='*60}")
    print(f"  Load Tester — Scenario: {scenario_name.upper()}")
    print(f"  Target: {settings.api_base_url}")
    print(f"  Max workers: {settings.max_workers}")
    print(f"  Token pool: {settings.token_pool_size}")
    print(f"{'='*60}\n")

    # 1. Connectivity check
    print("[runner] Checking API connectivity...")
    if not _check_connectivity():
        print("[runner] ERROR: Cannot reach the API. Aborting.")
        sys.exit(1)
    print("[runner] API is reachable.\n")

    # 2. Initialize token pool
    await token_pool.initialize(settings.token_pool_size)
    if len(token_pool) == 0:
        print("[runner] ERROR: Token pool is empty. Aborting.")
        sys.exit(1)

    # 3. Start dashboard in background thread
    dashboard_thread = threading.Thread(target=_start_dashboard, daemon=True)
    dashboard_thread.start()
    print(f"\n[runner] Dashboard running at http://0.0.0.0:{settings.dashboard_port}\n")
    await asyncio.sleep(1.0)  # give uvicorn a moment to bind

    # 4. Prepare metrics store
    metrics_store.reset()
    metrics_store.status = TestStatus.running
    metrics_store.scenario_name = scenario_name
    metrics_store.started_at = time.time()

    # 5. Start snapshot loop
    stop_snapshot = asyncio.Event()
    snapshot_task = asyncio.create_task(_run_metrics_snapshot_loop(stop_snapshot))

    # 6. Run scenario
    scenario = _get_scenario(scenario_name)
    try:
        await scenario.run()
    except KeyboardInterrupt:
        print("\n[runner] Interrupted by user.")
    finally:
        stop_snapshot.set()
        await snapshot_task

    # 7. Finalize
    metrics_store.finished_at = time.time()
    metrics_store.status = TestStatus.finished

    # 8. Save report
    print("\n[runner] Saving report...")
    os.makedirs(settings.results_dir, exist_ok=True)
    json_path, csv_path = metrics_store.save_report()
    print(f"[runner] JSON report: {json_path}")
    print(f"[runner] CSV  report: {csv_path}")

    report = metrics_store.build_report()
    print(f"\n{'='*60}")
    print(f"  RESULTS SUMMARY")
    print(f"  Total requests : {report['total_requests']}")
    print(f"  Total errors   : {report['total_errors']}")
    print(f"  Avg RPS        : {report['avg_rps']}")
    print(f"  Peak RPS       : {report['peak_rps']}")
    print(f"  Latency P50    : {report['latency']['p50']}ms")
    print(f"  Latency P95    : {report['latency']['p95']}ms")
    print(f"  Latency P99    : {report['latency']['p99']}ms")
    print(f"  Duration       : {report['duration_s']}s")
    print(f"{'='*60}\n")

    print(f"[runner] Dashboard still available at http://0.0.0.0:{settings.dashboard_port}")
    print("[runner] Press Ctrl+C to exit.")
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        pass


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
