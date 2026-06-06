from __future__ import annotations

import asyncio

from load_tester.core.config import settings
from load_tester.core.metrics import metrics_store
from load_tester.scenarios.base import BaseScenario, _worker_loop


class SpikeScenario(BaseScenario):
    name = "spike"

    async def run(self) -> None:
        # Phase 1: baseline load
        print(f"[spike] Phase 1 — base load ({settings.spike_base_workers} workers, {settings.spike_base_before_s}s)")
        await self._run_fixed_workers(settings.spike_base_workers, settings.spike_base_before_s)

        # Phase 2: spike
        print(f"[spike] Phase 2 — SPIKE ({settings.spike_peak_workers} workers, {settings.spike_peak_duration_s}s)")
        await self._run_fixed_workers(settings.spike_peak_workers, settings.spike_peak_duration_s)

        # Phase 3: return to baseline and observe recovery
        print(f"[spike] Phase 3 — recovery ({settings.spike_base_workers} workers, {settings.spike_base_after_s}s)")
        await self._run_fixed_workers(settings.spike_base_workers, settings.spike_base_after_s)

        print("[spike] Done")
