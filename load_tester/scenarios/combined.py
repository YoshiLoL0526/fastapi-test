from __future__ import annotations

import asyncio

from load_tester.scenarios.base import BaseScenario
from load_tester.scenarios.ramp_up import RampUpScenario
from load_tester.scenarios.spike import SpikeScenario
from load_tester.scenarios.sustained import SustainedScenario

_REST_BETWEEN_S = 10.0


class CombinedScenario(BaseScenario):
    name = "combined"

    async def run(self) -> None:
        print("[combined] === Starting combined scenario ===")

        print("[combined] --- Ramp Up ---")
        await RampUpScenario().run()

        print(f"[combined] Resting {_REST_BETWEEN_S}s...")
        await asyncio.sleep(_REST_BETWEEN_S)

        print("[combined] --- Sustained Load ---")
        await SustainedScenario().run()

        print(f"[combined] Resting {_REST_BETWEEN_S}s...")
        await asyncio.sleep(_REST_BETWEEN_S)

        print("[combined] --- Spike ---")
        await SpikeScenario().run()

        print("[combined] === Done ===")
