"""Brave Search API booster (paid)."""

from __future__ import annotations

import os

import httpx

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveAdapter(AdapterBase):
    name = "brave"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bool(os.environ.get("BRAVE_API_KEY"))

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        key = os.environ.get("BRAVE_API_KEY")
        if not key:
            raise AdapterUnavailable("brave", "BRAVE_API_KEY 未设置", hint="omnireach setup brave")
        headers = {"Accept": "application/json", "X-Subscription-Token": key}
        params = {"q": query, "count": limit}
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(BRAVE_URL, headers=headers, params=params)
            except httpx.HTTPError as e:
                raise AdapterUnavailable("brave", f"http error: {e}") from e
        if resp.status_code == 401:
            raise AdapterUnavailable("brave", "API Key 无效 (401)")
        if resp.status_code == 429:
            raise AdapterUnavailable("brave", "rate limited (429)")
        if resp.status_code >= 500:
            raise AdapterUnavailable("brave", f"upstream {resp.status_code}")
        hits = resp.json().get("web", {}).get("results", [])[:limit]
        return [
            SearchResult(
                source="brave",
                adapter="brave-api",
                title=h.get("title") or "",
                url=h.get("url") or "",
                content=h.get("description") or "",
                ts=h.get("age"),
                cost="paid",
                raw=h,
            )
            for h in hits
        ]
