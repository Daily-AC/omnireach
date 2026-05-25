"""WeChat 公众号 adapter — Exa domain-filtered search (booster, needs EXA_API_KEY)."""

from __future__ import annotations

import os

import httpx

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult

EXA_URL = "https://api.exa.ai/search"
DOMAINS = ["mp.weixin.qq.com"]


class WeChatAdapter(AdapterBase):
    name = "wechat"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bool(os.environ.get("EXA_API_KEY"))

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        key = os.environ.get("EXA_API_KEY")
        if not key:
            raise AdapterUnavailable("wechat", "EXA_API_KEY 未设置", hint="omnireach setup wechat")
        headers = {"x-api-key": key, "Content-Type": "application/json"}
        body = {"query": query, "numResults": limit, "type": "auto",
                "includeDomains": DOMAINS}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(EXA_URL, json=body, headers=headers)
            except httpx.HTTPError as e:
                raise AdapterUnavailable("wechat", f"http error: {e}") from e
        if resp.status_code == 401:
            raise AdapterUnavailable("wechat", "API Key 无效 (401)")
        if resp.status_code == 429:
            raise AdapterUnavailable("wechat", "rate limited (429)")
        if resp.status_code >= 500:
            raise AdapterUnavailable("wechat", f"upstream {resp.status_code}")
        data = resp.json()
        results: list[SearchResult] = []
        for hit in data.get("results", [])[:limit]:
            results.append(SearchResult(
                source="wechat",
                adapter="exa-api",
                title=hit.get("title") or "",
                url=hit.get("url") or "",
                content=hit.get("text") or "",
                author=hit.get("author"),
                ts=hit.get("publishedDate"),
                cost="paid",
                raw=hit,
            ))
        return results
