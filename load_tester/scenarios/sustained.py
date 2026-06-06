from __future__ import annotations

from load_tester.core.config import settings
from load_tester.scenarios.base import BaseScenario


class SustainedScenario(BaseScenario):
    name = "sustained"

    async def run(self) -> None:
        workers = min(settings.sustained_workers, settings.max_workers)
        duration = settings.sustained_duration_s
        print(f"[sustained] Running {workers} workers for {duration}s")
        await self._run_fixed_workers(workers, duration)
        print("[sustained] Done")
