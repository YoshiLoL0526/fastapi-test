from __future__ import annotations

import asyncio

from load_tester.core.config import settings
from load_tester.core.metrics import metrics_store
from load_tester.scenarios.base import BaseScenario, _worker_loop


class RampUpScenario(BaseScenario):
    name = "ramp_up"

    async def run(self) -> None:
        stop = asyncio.Event()
        tasks: list[asyncio.Task] = []
        worker_id = 0

        # Start with initial batch
        initial = min(settings.ramp_initial_workers, settings.max_workers)
        for i in range(initial):
            tasks.append(asyncio.create_task(_worker_loop(worker_id + i, stop)))
        worker_id += initial
        metrics_store.workers_active = initial
        metrics_store.max_workers_reached = initial

        print(f"[ramp_up] Started with {initial} workers")

        elapsed = 0.0
        while worker_id < settings.max_workers:
            await asyncio.sleep(settings.ramp_step_interval_s)
            elapsed += settings.ramp_step_interval_s

            step = min(settings.ramp_step_workers, settings.max_workers - worker_id)
            if step <= 0:
                break

            for i in range(step):
                tasks.append(asyncio.create_task(_worker_loop(worker_id + i, stop)))
            worker_id += step
            metrics_store.workers_active = worker_id
            metrics_store.max_workers_reached = max(metrics_store.max_workers_reached, worker_id)
            print(f"[ramp_up] +{step} workers → {worker_id} total (elapsed {elapsed:.0f}s)")

        # Hold at max for one more interval
        await asyncio.sleep(settings.ramp_step_interval_s)
        stop.set()
        metrics_store.workers_active = 0
        await asyncio.gather(*tasks, return_exceptions=True)
        print("[ramp_up] Done")
