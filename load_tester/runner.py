from __future__ import annotations

import asyncio
import os
import time

import httpx

from load_tester.core.auth import token_pool
from load_tester.core.config import settings
from load_tester.core.metrics import TestStatus, metrics_store


def _check_connectivity() -> bool:
    try:
        resp = httpx.get(f"{settings.api_base_url}/health/", timeout=5.0, follow_redirects=True)
        return resp.status_code == 200
    except Exception as exc:
        print(f"[runner] API not reachable: {exc}")
        return False


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
        raise ValueError(f"Unknown scenario '{name}'. Valid: {list(mapping)}")
    return cls()


async def run_test(scenario_name: str) -> None:
    """Run a complete load test. Launched as an asyncio task from the dashboard."""
    print(f"\n{'='*60}")
    print(f"  Load Tester — Scenario: {scenario_name.upper()}")
    print(f"  Target: {settings.api_base_url}")
    print(f"  Max workers: {settings.max_workers}")
    print(f"{'='*60}\n")

    # 1. Connectivity
    print("[runner] Checking API connectivity...")
    if not _check_connectivity():
        print("[runner] ERROR: Cannot reach the API.")
        metrics_store.status = TestStatus.idle
        return
    print("[runner] API is reachable.\n")

    # 2. Token pool
    await token_pool.initialize(settings.token_pool_size)
    if len(token_pool) == 0:
        print("[runner] ERROR: Token pool is empty.")
        metrics_store.status = TestStatus.idle
        return

    # 3. Prepare metrics
    metrics_store.reset()
    metrics_store.status = TestStatus.running
    metrics_store.scenario_name = scenario_name
    metrics_store.started_at = time.time()

    # 4. Run scenario — CancelledError propagates cleanly when /stop is called
    scenario = _get_scenario(scenario_name)
    try:
        await scenario.run()
    except asyncio.CancelledError:
        print("\n[runner] Test stopped by user.")
    except Exception as exc:
        print(f"\n[runner] Scenario error: {exc}")

    # 5. Finalize
    metrics_store.finished_at = time.time()
    metrics_store.status = TestStatus.finished

    # 6. Save report
    print("\n[runner] Saving report...")
    os.makedirs(settings.results_dir, exist_ok=True)
    json_path, csv_path = metrics_store.save_report()
    print(f"[runner] JSON: {json_path}")
    print(f"[runner] CSV:  {csv_path}")

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


def run() -> None:
    """Entry point: start the dashboard. Tests are launched from the UI."""
    from load_tester.ui.main import create_app
    import uvicorn

    app = create_app()
    print(f"\n[tester] Dashboard → http://0.0.0.0:{settings.dashboard_port}")
    print(f"[tester] Open   http://localhost:{settings.dashboard_port} in your browser.")
    print(f"[tester] Target API: {settings.api_base_url}\n")

    uvicorn.run(app, host="0.0.0.0", port=settings.dashboard_port, log_level="warning")
