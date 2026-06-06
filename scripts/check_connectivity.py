#!/usr/bin/env python3
"""Verify API connectivity before running the load tester.

Checks that the API is reachable, the health endpoint responds correctly,
and the database is connected. Exits with code 0 on success, 1 on failure.

Usage:
    python scripts/check_connectivity.py [BASE_URL]

    BASE_URL defaults to $API_BASE_URL env var, then http://localhost:8000
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx


DEFAULT_BASE_URL = "http://localhost:8000"
TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


async def check(base_url: str) -> bool:
    url = base_url.rstrip("/")
    health_url = f"{url}/health/"

    print(f"Target : {url}")
    print(f"Probe  : {health_url}\n")

    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"Attempt {attempt}/{MAX_RETRIES}…", end=" ", flush=True)
            t0 = time.perf_counter()
            try:
                response = await client.get(health_url)
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
            except httpx.ConnectError as exc:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
                print(f"FAIL  ({elapsed_ms} ms)")
                print(f"  Connection refused: {exc}")
                if attempt < MAX_RETRIES:
                    print(f"  Retrying in {RETRY_DELAY_SECONDS}s…")
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue
            except httpx.TimeoutException:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
                print(f"FAIL  ({elapsed_ms} ms)")
                print(f"  Request timed out after {TIMEOUT_SECONDS}s")
                if attempt < MAX_RETRIES:
                    print(f"  Retrying in {RETRY_DELAY_SECONDS}s…")
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue
            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
                print(f"FAIL  ({elapsed_ms} ms)")
                print(f"  Unexpected error: {exc}")
                if attempt < MAX_RETRIES:
                    print(f"  Retrying in {RETRY_DELAY_SECONDS}s…")
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue

            if response.status_code != 200:
                print(f"FAIL  ({elapsed_ms} ms)")
                print(f"  HTTP {response.status_code}: {response.text[:200]}")
                if attempt < MAX_RETRIES:
                    print(f"  Retrying in {RETRY_DELAY_SECONDS}s…")
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue

            # Parse health payload
            try:
                payload = response.json()
            except Exception:
                print(f"FAIL  ({elapsed_ms} ms)")
                print("  Could not parse JSON response")
                continue

            status = payload.get("status", "unknown")
            db = payload.get("database", {})
            db_ok = db.get("connected", False)
            db_latency = db.get("latency_ms")
            uptime = payload.get("uptime_seconds")

            if status == "ok" and db_ok:
                print(f"OK    ({elapsed_ms} ms)")
                print()
                print("Results:")
                print(f"  API status   : {status}")
                print(f"  DB connected : {db_ok}")
                print(f"  DB latency   : {db_latency} ms")
                print(f"  Uptime       : {uptime}s")
                print()
                print("✅ API is reachable and healthy. Ready to run the load tester.")
                return True

            # Degraded but reachable
            print(f"DEGRADED  ({elapsed_ms} ms)")
            print(f"  API status   : {status}")
            print(f"  DB connected : {db_ok}")
            if not db_ok:
                print("  Database is not connected — check DATABASE_URL and the DB server.")
            if attempt < MAX_RETRIES:
                print(f"  Retrying in {RETRY_DELAY_SECONDS}s…")
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    print()
    print("❌ API did not pass connectivity checks after all retries.")
    print()
    print("Checklist:")
    print(f"  1. Is the API server running?  (e.g. uvicorn api.main:app --host 0.0.0.0 --port 8000)")
    print(f"  2. Is the target URL correct?  ({base_url})")
    print( "  3. Is the database server reachable from the API host?")
    print( "  4. Are there firewall rules blocking the connection?")
    return False


async def main() -> None:
    base_url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("API_BASE_URL", DEFAULT_BASE_URL)
    )
    ok = await check(base_url)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
