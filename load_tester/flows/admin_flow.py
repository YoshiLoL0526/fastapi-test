from __future__ import annotations

import asyncio
import random

from load_tester.core.auth import token_pool
from load_tester.core.client import LoadTestClient
from load_tester.core.config import settings
from load_tester.core.metrics import metrics_store


async def _think() -> None:
    delay = random.randint(settings.think_time_min_ms, settings.think_time_max_ms) / 1000
    await asyncio.sleep(delay)


ORDER_STATUSES = ["processing", "shipped", "delivered"]


async def run(worker_id: int) -> None:
    """Admin operations flow: orders, stock adjustments, product updates."""
    admin_token = token_pool.admin_token
    if not admin_token:
        return

    async with LoadTestClient(worker_id, "admin_flow", admin_token) as client:

        # 1. List pending orders
        result, orders_body = await client.get("/orders/admin/all", params={
            "page": 1,
            "page_size": 20,
            "status_filter": "pending",
        })
        metrics_store.record(result)
        await _think()

        # 2. Update status of 1-3 orders
        orders: list[dict] = []
        if orders_body and orders_body.get("items"):
            orders = orders_body["items"]

        for order in random.sample(orders, k=min(random.randint(1, 3), len(orders))):
            new_status = random.choice(ORDER_STATUSES)
            result, _ = await client.patch(f"/orders/admin/{order['id']}/status", json={
                "status": new_status,
            })
            metrics_store.record(result)
            await _think()

        # 3. Check low-stock report
        result, low_stock_body = await client.get("/inventory/low-stock", params={
            "page": 1, "page_size": 20,
        })
        metrics_store.record(result)
        await _think()

        # 4. Adjust stock for a few low-stock products
        low_items: list[dict] = []
        if low_stock_body and low_stock_body.get("items"):
            low_items = low_stock_body["items"]

        for item in random.sample(low_items, k=min(2, len(low_items))):
            pid = item.get("product_id")
            if pid:
                result, _ = await client.post(f"/inventory/{pid}/adjust", json={
                    "delta": random.randint(10, 50),
                    "reason": "restock",
                })
                metrics_store.record(result)
                await _think()

        # 5. List products and update one
        result, prod_body = await client.get("/products/", params={"page": 1, "page_size": 20})
        metrics_store.record(result)
        await _think()

        products: list[dict] = []
        if prod_body and prod_body.get("items"):
            products = prod_body["items"]

        if products:
            prod = random.choice(products)
            new_price = round(random.uniform(10.0, 500.0), 2)
            result, _ = await client.put(f"/products/{prod['id']}", json={
                "price": new_price,
            })
            metrics_store.record(result)
