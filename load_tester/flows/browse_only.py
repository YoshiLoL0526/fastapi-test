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


async def run(worker_id: int) -> None:
    """Browse-only flow: list products, view details, read reviews, search."""
    token_entry = await token_pool.acquire()

    async with LoadTestClient(worker_id, "browse_only", token_entry.access_token) as client:

        # 1. List categories
        result, cat_body = await client.get("/categories/")
        metrics_store.record(result)
        await _think()

        categories: list[dict] = []
        if cat_body and isinstance(cat_body, list):
            for cat in cat_body:
                categories.append(cat)
                categories.extend(cat.get("children", []))

        # 2. List products with varied filters / ordering
        sort_options = ["created_at", "price", "rating"]
        sort_dirs = ["asc", "desc"]
        params: dict = {
            "page": random.randint(1, 3),
            "page_size": random.choice([10, 20]),
            "sort_by": random.choice(sort_options),
            "sort_dir": random.choice(sort_dirs),
        }
        if categories and random.random() < 0.6:
            params["category_id"] = random.choice(categories)["id"]
        if random.random() < 0.3:
            params["min_price"] = random.choice([5, 10, 25])
        if random.random() < 0.3:
            params["max_price"] = random.choice([100, 200, 500])
        if random.random() < 0.4:
            params["in_stock"] = True

        result, body = await client.get("/products/", params=params)
        metrics_store.record(result)
        await _think()

        products: list[dict] = []
        if body and body.get("items"):
            products = body["items"]

        if not products:
            return

        # 3. View details of several products
        sampled = random.sample(products, k=min(random.randint(2, 5), len(products)))
        for prod in sampled:
            result, _ = await client.get(f"/products/{prod['id']}")
            metrics_store.record(result)
            await _think()

            # 4. Read reviews for this product
            result, _ = await client.get(
                f"/reviews/products/{prod['id']}",
                params={"page": 1, "page_size": 10},
            )
            metrics_store.record(result)
            await _think()

        # 5. Text search
        search_terms = ["laptop", "phone", "shirt", "book", "headphones", "chair", "watch"]
        result, _ = await client.get("/products/", params={
            "search": random.choice(search_terms),
            "page": 1,
            "page_size": 10,
        })
        metrics_store.record(result)
