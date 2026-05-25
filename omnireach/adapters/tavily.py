"""Tavily Search API booster (paid)."""

from __future__ import annotations

import os

import httpx

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult

TAVILY_URL = "https://api.tavily.com/search"


class TavilyAdapter(AdapterBase):
    name = "tavily"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bool(os.environ.get("TAVILY_API_KEY"))

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        key = os.environ.get("TAVILY_API_KEY")
        if not key:
            raise AdapterUnavailable("tavily", "TAVILY_API_KEY 未设置", hint="omnireach setup tavily")
        payload = {"api_key": key, "query": query, "max_results": limit}
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.post(TAVILY_URL, json=payload)
            except httpx.HTTPError as e:
                raise AdapterUnavailable("tavily", f"http error: {e}") from e
        if resp.status_code == 401:
            raise AdapterUnavailable("tavily", "API Key 无效 (401)")
        if resp.status_code == 429:
            raise AdapterUnavailable("tavily", "rate limited (429)")
        if resp.status_code >= 500:
            raise AdapterUnavailable("tavily", f"upstream {resp.status_code}")
        data = resp.json()
        results: list[SearchResult] = []
        for hit in data.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    source="tavily",
                    adapter="tavily-api",
                    title=hit.get("title") or "",
                    url=hit.get("url") or "",
                    content=hit.get("content") or "",
                    ts=hit.get("published_date"),
                    cost="paid",
                    raw=hit,
                )
            )
        return results
