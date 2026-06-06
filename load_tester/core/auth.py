from __future__ import annotations

import asyncio
import random
import string
import time
from dataclasses import dataclass

import httpx

from load_tester.core.config import settings


@dataclass
class TokenEntry:
    user_id: str
    email: str
    access_token: str
    refresh_token: str
    expires_at: float  # unix timestamp
    address_id: str = ""


def _random_email() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"loadtest_{suffix}@test.example"


class TokenPool:
    """Pre-warmed pool of authenticated tokens for load test workers."""

    def __init__(self) -> None:
        self._tokens: list[TokenEntry] = []
        self._lock = asyncio.Lock()
        self._admin_token: str | None = None

    async def initialize(self, size: int) -> None:
        """Create/login `size` test users and fill the pool."""
        print(f"[auth] Initializing token pool with {size} users...")
        async with httpx.AsyncClient(base_url=settings.api_base_url, timeout=30.0) as client:
            await self._warm_admin(client)
            tasks = [self._provision_user(client, i) for i in range(size)]
            entries = await asyncio.gather(*tasks, return_exceptions=True)

        for entry in entries:
            if isinstance(entry, TokenEntry):
                self._tokens.append(entry)
            else:
                print(f"[auth] Warning: failed to provision user: {entry}")

        print(f"[auth] Pool ready with {len(self._tokens)} tokens.")

    async def _warm_admin(self, client: httpx.AsyncClient) -> None:
        resp = await client.post("/auth/login", json={
            "email": settings.admin_email,
            "password": settings.admin_password,
        })
        if resp.status_code == 200:
            data = resp.json()
            self._admin_token = data["access_token"]

    async def _provision_user(self, client: httpx.AsyncClient, index: int) -> TokenEntry:
        email = f"loadtest_{index:04d}@test.example"
        password = "LoadTest1234!"

        # Try login first, register if not found
        resp = await client.post("/auth/login", json={"email": email, "password": password})
        if resp.status_code != 200:
            reg_resp = await client.post("/auth/register", json={
                "email": email,
                "username": f"loadtest_{index:04d}",
                "password": password,
                "full_name": f"Load Tester {index}",
            })
            if reg_resp.status_code not in (200, 201):
                raise RuntimeError(f"Could not register user {email}: {reg_resp.text}")
            resp = await client.post("/auth/login", json={"email": email, "password": password})

        data = resp.json()
        entry = TokenEntry(
            user_id=data.get("user", {}).get("id", ""),
            email=email,
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=time.time() + (settings.request_timeout_s * 60),
        )
        await self._ensure_address(client, entry)
        return entry

    async def _ensure_address(self, client: httpx.AsyncClient, entry: TokenEntry) -> None:
        """Create a shipping address for the user if none exists."""
        headers = {"Authorization": f"Bearer {entry.access_token}"}
        resp = await client.get("/users/me/addresses", headers=headers)
        if resp.status_code == 200:
            addresses = resp.json()
            if addresses:
                entry.address_id = addresses[0]["id"]
                return
        create_resp = await client.post("/users/me/addresses", headers=headers, json={
            "line1": "123 Load Test Street",
            "city": "Test City",
            "state": "CA",
            "country": "US",
            "zip_code": "90001",
            "is_default": True,
        })
        if create_resp.status_code in (200, 201):
            entry.address_id = create_resp.json()["id"]

    async def acquire(self) -> TokenEntry:
        """Get a token from the pool (round-robin)."""
        async with self._lock:
            if not self._tokens:
                raise RuntimeError("Token pool is empty")
            token = self._tokens.pop(0)
            self._tokens.append(token)
        return token

    async def refresh(self, entry: TokenEntry) -> TokenEntry:
        """Refresh an expired token and return the updated entry."""
        async with httpx.AsyncClient(base_url=settings.api_base_url, timeout=15.0) as client:
            resp = await client.post("/auth/refresh", json={"refresh_token": entry.refresh_token})
            if resp.status_code == 200:
                data = resp.json()
                entry.access_token = data["access_token"]
                entry.refresh_token = data["refresh_token"]
                entry.expires_at = time.time() + (settings.request_timeout_s * 60)
            else:
                # Re-login
                resp2 = await client.post("/auth/login", json={"email": entry.email, "password": "LoadTest1234!"})
                if resp2.status_code == 200:
                    data = resp2.json()
                    entry.access_token = data["access_token"]
                    entry.refresh_token = data["refresh_token"]
                    entry.expires_at = time.time() + (settings.request_timeout_s * 60)
        return entry

    @property
    def admin_token(self) -> str | None:
        return self._admin_token

    def __len__(self) -> int:
        return len(self._tokens)


# Module-level singleton
token_pool = TokenPool()
