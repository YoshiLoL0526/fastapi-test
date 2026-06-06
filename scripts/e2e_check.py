#!/usr/bin/env python3
"""End-to-end pre-flight check for the FastAPI Benchmark.

Exercises the complete purchase flow end-to-end:
  health → categories → products → admin auth → register user →
  user auth → address → cart → checkout → order list → inventory

Exits 0 if all checks pass, 1 if any fail.

Usage:
    python scripts/e2e_check.py [BASE_URL]

    BASE_URL defaults to $API_BASE_URL env var, then http://localhost:8000

Requires the DB to be seeded (uv run seed-db) and the API to be running.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from dataclasses import dataclass, field

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
TIMEOUT = 10.0

_TEST_EMAIL = f"e2e_{uuid.uuid4().hex[:8]}@test.example"
_TEST_PASSWORD = "E2eTest1234!"


@dataclass
class Result:
    name: str
    ok: bool
    elapsed_ms: float
    detail: str = ""


@dataclass
class Suite:
    results: list[Result] = field(default_factory=list)

    def record(self, name: str, ok: bool, elapsed_ms: float, detail: str = "") -> None:
        self.results.append(Result(name, ok, elapsed_ms, detail))
        icon = " OK " if ok else "FAIL"
        detail_str = f"  — {detail}" if detail else ""
        print(f"  [{icon}]  {name} ({elapsed_ms:.0f}ms){detail_str}")

    def summary(self) -> tuple[int, int]:
        passed = sum(1 for r in self.results if r.ok)
        return passed, len(self.results)


async def run_checks(base: str) -> Suite:
    suite = Suite()
    url = base.rstrip("/")
    print(f"\nTarget: {url}\n")

    async with httpx.AsyncClient(base_url=url, timeout=TIMEOUT, follow_redirects=True) as client:

        # ── 1. Health ────────────────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            r = await client.get("/health/")
            ms = (time.perf_counter() - t0) * 1000
            data = r.json()
            ok = r.status_code == 200 and data.get("status") == "ok"
            db_ms = data.get("database", {}).get("latency_ms", "?")
            suite.record("Health endpoint", ok, ms,
                         f"db_latency={db_ms}ms" if ok else r.text[:80])
        except Exception as exc:
            suite.record("Health endpoint", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])
            print("\n  API is not reachable — aborting.\n")
            return suite

        # ── 2. Categories ────────────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            r = await client.get("/categories/")
            ms = (time.perf_counter() - t0) * 1000
            cats = r.json() if r.status_code == 200 else []
            ok = r.status_code == 200 and len(cats) > 0
            suite.record("Category list (seed data)", ok, ms,
                         f"{len(cats)} root categories" if ok else r.text[:80])
        except Exception as exc:
            suite.record("Category list (seed data)", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])

        # ── 3. Products ──────────────────────────────────────────────────────
        t0 = time.perf_counter()
        first_product_id: str | None = None
        try:
            r = await client.get("/products/", params={"page_size": 5})
            ms = (time.perf_counter() - t0) * 1000
            data = r.json() if r.status_code == 200 else {}
            items = data.get("items", [])
            ok = r.status_code == 200 and len(items) > 0
            if ok:
                first_product_id = str(items[0]["id"])
            suite.record("Product list (seed data)", ok, ms,
                         f"{data.get('total', 0)} products" if ok else r.text[:80])
        except Exception as exc:
            suite.record("Product list (seed data)", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])

        # ── 4. Product search ────────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            r = await client.get("/products/", params={"search": "a", "page_size": 3})
            ms = (time.perf_counter() - t0) * 1000
            ok = r.status_code == 200
            suite.record("Product search", ok, ms,
                         f"{r.json().get('total', 0)} results" if ok else r.text[:80])
        except Exception as exc:
            suite.record("Product search", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])

        # ── 5. Admin login ───────────────────────────────────────────────────
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
        admin_password = os.environ.get("ADMIN_PASSWORD", "admin1234")
        admin_token: str | None = None

        t0 = time.perf_counter()
        try:
            r = await client.post("/auth/login", json={"email": admin_email, "password": admin_password})
            ms = (time.perf_counter() - t0) * 1000
            ok = r.status_code == 200
            if ok:
                admin_token = r.json()["access_token"]
            suite.record("Admin login", ok, ms, "token obtained" if ok else r.text[:80])
        except Exception as exc:
            suite.record("Admin login", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])

        if admin_token:
            t0 = time.perf_counter()
            try:
                r = await client.get("/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
                ms = (time.perf_counter() - t0) * 1000
                ok = r.status_code == 200
                suite.record("Admin /auth/me", ok, ms,
                             r.json().get("email", "") if ok else r.text[:80])
            except Exception as exc:
                suite.record("Admin /auth/me", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])

        # ── 6. Register test user ────────────────────────────────────────────
        user_token: str | None = None
        t0 = time.perf_counter()
        try:
            r = await client.post("/auth/register", json={
                "email": _TEST_EMAIL,
                "password": _TEST_PASSWORD,
                "full_name": "E2E Test User",
            })
            ms = (time.perf_counter() - t0) * 1000
            ok = r.status_code == 201
            suite.record("Register test user", ok, ms,
                         _TEST_EMAIL if ok else r.text[:80])
        except Exception as exc:
            suite.record("Register test user", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])

        # ── 7. Login as test user ────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            r = await client.post("/auth/login", json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD})
            ms = (time.perf_counter() - t0) * 1000
            ok = r.status_code == 200
            if ok:
                user_token = r.json()["access_token"]
            suite.record("Login as test user", ok, ms, "token obtained" if ok else r.text[:80])
        except Exception as exc:
            suite.record("Login as test user", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])

        if user_token and first_product_id:
            auth = {"Authorization": f"Bearer {user_token}"}

            # ── 8. Create shipping address ───────────────────────────────────
            t0 = time.perf_counter()
            address_id: str | None = None
            try:
                r = await client.post("/users/me/addresses", headers=auth, json={
                    "line1": "123 Test Street",
                    "city": "Test City",
                    "state": "TC",
                    "country": "US",
                    "zip_code": "00000",
                    "is_default": True,
                })
                ms = (time.perf_counter() - t0) * 1000
                ok = r.status_code == 201
                if ok:
                    address_id = str(r.json()["id"])
                suite.record("Create shipping address", ok, ms,
                             f"address_id={address_id}" if ok else r.text[:80])
            except Exception as exc:
                suite.record("Create shipping address", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])

            # ── 9. Get cart ──────────────────────────────────────────────────
            t0 = time.perf_counter()
            try:
                r = await client.get("/cart/", headers=auth)
                ms = (time.perf_counter() - t0) * 1000
                ok = r.status_code == 200
                suite.record("Get cart", ok, ms, "empty cart" if ok else r.text[:80])
            except Exception as exc:
                suite.record("Get cart", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])

            # ── 10. Add item to cart ─────────────────────────────────────────
            t0 = time.perf_counter()
            try:
                r = await client.post("/cart/items", headers=auth,
                                      json={"product_id": first_product_id, "quantity": 1})
                ms = (time.perf_counter() - t0) * 1000
                ok = r.status_code == 201
                n = len(r.json().get("items", [])) if ok else 0
                suite.record("Add item to cart", ok, ms,
                             f"{n} item(s) in cart" if ok else r.text[:80])
            except Exception as exc:
                suite.record("Add item to cart", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])

            # ── 11. Checkout ─────────────────────────────────────────────────
            if address_id:
                t0 = time.perf_counter()
                try:
                    r = await client.post("/orders/", headers=auth,
                                          json={"shipping_address_id": address_id})
                    ms = (time.perf_counter() - t0) * 1000
                    ok = r.status_code == 201
                    order_id = str(r.json()["id"]) if ok else None
                    suite.record("Checkout (create order)", ok, ms,
                                 f"order_id={order_id}" if ok else r.text[:80])
                except Exception as exc:
                    suite.record("Checkout (create order)", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])
            else:
                suite.record("Checkout (create order)", False, 0, "skipped — no address_id")

            # ── 12. List orders ──────────────────────────────────────────────
            t0 = time.perf_counter()
            try:
                r = await client.get("/orders/", headers=auth)
                ms = (time.perf_counter() - t0) * 1000
                ok = r.status_code == 200
                suite.record("List user orders", ok, ms,
                             f"{r.json().get('total', 0)} order(s)" if ok else r.text[:80])
            except Exception as exc:
                suite.record("List user orders", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])

        # ── 13. Inventory (admin) ────────────────────────────────────────────
        if admin_token and first_product_id:
            t0 = time.perf_counter()
            try:
                r = await client.get(f"/inventory/{first_product_id}",
                                     headers={"Authorization": f"Bearer {admin_token}"})
                ms = (time.perf_counter() - t0) * 1000
                ok = r.status_code == 200
                qty = r.json().get("quantity_available") if ok else None
                suite.record("Inventory check (admin)", ok, ms,
                             f"quantity_available={qty}" if ok else r.text[:80])
            except Exception as exc:
                suite.record("Inventory check (admin)", False, (time.perf_counter() - t0) * 1000, str(exc)[:80])

    return suite


async def main() -> None:
    base_url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("API_BASE_URL", DEFAULT_BASE_URL)
    )

    t_total = time.perf_counter()
    suite = await run_checks(base_url)
    elapsed_total = (time.perf_counter() - t_total) * 1000

    passed, total = suite.summary()
    failed = total - passed

    print(f"\n{'─' * 52}")
    print(f"  {passed}/{total} checks passed  ({elapsed_total:.0f}ms total)")
    if failed:
        print(f"  {failed} failed:")
        for r in suite.results:
            if not r.ok:
                print(f"    · {r.name}: {r.detail}")
        print()
        print("  Fix the failing checks before running the load tester.")
    else:
        print()
        print("  ✓ All checks passed. System is ready for load testing.")
    print(f"{'─' * 52}\n")

    sys.exit(0 if failed == 0 else 1)


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
