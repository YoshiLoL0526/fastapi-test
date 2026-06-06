from __future__ import annotations

import asyncio
import random
import time
from typing import Callable, Coroutine, Any

from load_tester.core.config import settings
from load_tester.core.metrics import TestStatus, metrics_store
from load_tester import flows


FlowFn = Callable[[int], Coroutine[Any, Any, None]]


def _pick_flow() -> FlowFn:
    roll = random.random()
    if roll < settings.flow_browse_and_buy_ratio:
        return flows.browse_and_buy.run
    elif roll < settings.flow_browse_and_buy_ratio + settings.flow_browse_only_ratio:
        return flows.browse_only.run
    return flows.admin_flow.run


async def _worker_loop(worker_id: int, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        flow = _pick_flow()
        try:
            await flow(worker_id)
        except Exception as exc:
            # Swallow so a single worker failure doesn't kill the scenario
            pass


class BaseScenario:
    name: str = "base"

    async def run(self) -> None:
        raise NotImplementedError

    async def _run_fixed_workers(self, num_workers: int, duration_s: float) -> None:
        """Run exactly `num_workers` concurrent workers for `duration_s` seconds."""
        stop = asyncio.Event()
        metrics_store.workers_active = num_workers
        metrics_store.max_workers_reached = max(metrics_store.max_workers_reached, num_workers)

        tasks = [asyncio.create_task(_worker_loop(i, stop)) for i in range(num_workers)]

        await asyncio.sleep(duration_s)
        stop.set()
        metrics_store.workers_active = 0
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _add_workers(
        self,
        existing_tasks: list[asyncio.Task],
        stop_event: asyncio.Event,
        from_id: int,
        count: int,
    ) -> list[asyncio.Task]:
        new_tasks = [
            asyncio.create_task(_worker_loop(from_id + i, stop_event))
            for i in range(count)
        ]
        existing_tasks.extend(new_tasks)
        total = len(existing_tasks)
        metrics_store.workers_active = total
        metrics_store.max_workers_reached = max(metrics_store.max_workers_reached, total)
        return existing_tasks
