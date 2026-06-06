from __future__ import annotations

import asyncio
import random

from load_tester.core.auth import TokenEntry, token_pool
from load_tester.core.client import LoadTestClient
from load_tester.core.config import settings
from load_tester.core.metrics import metrics_store


async def _think() -> None:
    delay = random.randint(settings.think_time_min_ms, settings.think_time_max_ms) / 1000
    await asyncio.sleep(delay)


async def run(worker_id: int) -> None:
    """Browse-and-buy flow: login → browse → cart → checkout → pay → review."""
    token_entry: TokenEntry = await token_pool.acquire()

    async with LoadTestClient(worker_id, "browse_and_buy", token_entry.access_token) as client:

        # 1. List categories and pick one
        result, body = await client.get("/categories/")
        metrics_store.record(result)
        await _think()

        categories: list[dict] = []
        if body and isinstance(body, list):
            flat: list[dict] = []
            for cat in body:
                flat.append(cat)
                flat.extend(cat.get("children", []))
            categories = [c for c in flat if c.get("id")]

        category_id = random.choice(categories)["id"] if categories else None

        # 2. List products in that category (with random filters)
        params: dict = {"page": 1, "page_size": 20}
        if category_id:
            params["category_id"] = category_id
        if random.random() < 0.4:
            params["min_price"] = random.choice([10, 20, 50])
        if random.random() < 0.3:
            params["in_stock"] = True
        sort_options = ["created_at", "price", "rating"]
        params["sort_by"] = random.choice(sort_options)

        result, body = await client.get("/products/", params=params)
        metrics_store.record(result)
        await _think()

        products: list[dict] = []
        if body and body.get("items"):
            products = body["items"]

        if not products:
            return

        # 3. View detail of 1-3 products
        sampled = random.sample(products, k=min(random.randint(1, 3), len(products)))
        viewed_product_ids = []
        for prod in sampled:
            result, _ = await client.get(f"/products/{prod['id']}")
            metrics_store.record(result)
            viewed_product_ids.append(prod["id"])
            await _think()

        # 4. Add 1-2 products to cart
        to_buy = random.sample(viewed_product_ids, k=min(random.randint(1, 2), len(viewed_product_ids)))
        for pid in to_buy:
            result, _ = await client.post("/cart/items", json={
                "product_id": pid,
                "quantity": random.randint(1, 2),
            })
            metrics_store.record(result)
            await _think()

        # 5. View cart
        result, cart_body = await client.get("/cart/")
        metrics_store.record(result)
        await _think()

        # 6. Checkout
        result, order_body = await client.post("/orders/", json={
            "shipping_address": "123 Test Street, Load City, LC 00000",
        })
        metrics_store.record(result)
        await _think()

        if result.is_error or not order_body:
            return

        order_id = order_body.get("id")
        if not order_id:
            return

        # 7. Process payment
        result, payment_body = await client.post("/payments/", json={"order_id": order_id})
        metrics_store.record(result)
        await _think()

        # 8. Check order status
        result, _ = await client.get(f"/orders/{order_id}")
        metrics_store.record(result)
        await _think()

        # 9. Leave a review on one of the purchased products (if payment succeeded)
        if payment_body and payment_body.get("status") == "completed" and to_buy:
            pid = random.choice(to_buy)
            result, _ = await client.post("/reviews/", json={
                "product_id": pid,
                "order_id": order_id,
                "rating": random.randint(3, 5),
                "title": "Great product",
                "body": "Really enjoyed this purchase. Would buy again.",
            })
            metrics_store.record(result)
