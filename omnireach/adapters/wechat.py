"""WeChat 公众号 adapter — Exa primary (paid), Sogou fallback (free, v0.9)."""

from __future__ import annotations
import logging
import os

import httpx

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.adapters._wechat_sogou import search_sogou
from omnireach.contract import SearchResult

log = logging.getLogger(__name__)

EXA_URL = "https://api.exa.ai/search"
DOMAINS = ["mp.weixin.qq.com"]


async def _search_exa(query: str, *, limit: int) -> list[SearchResult]:
    """Exa-backed search path — primary (paid)."""
    key = os.environ.get("EXA_API_KEY")
    if not key:
        raise AdapterUnavailable("wechat:exa", "EXA_API_KEY 未设置", hint="omnireach setup wechat")
    headers = {"x-api-key": key, "Content-Type": "application/json"}
    body = {"query": query, "numResults": limit, "type": "auto", "includeDomains": DOMAINS}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(EXA_URL, json=body, headers=headers)
        except httpx.HTTPError as e:
            raise AdapterUnavailable("wechat:exa", f"http error: {e}") from e
    if resp.status_code == 401:
        raise AdapterUnavailable("wechat:exa", "API Key 无效 (401)")
    if resp.status_code == 429:
        raise AdapterUnavailable("wechat:exa", "rate limited (429)")
    if resp.status_code >= 500:
        raise AdapterUnavailable("wechat:exa", f"upstream {resp.status_code}")
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


class WeChatAdapter(AdapterBase):
    name = "wechat"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        # Either backend works → adapter is always ready
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        # Priority: Exa (if EXA_API_KEY set) > Sogou (free fallback)
        if os.environ.get("EXA_API_KEY"):
            try:
                return await _search_exa(query, limit=limit)
            except AdapterUnavailable as e:
                log.warning("wechat: Exa unavailable (%s), falling back to Sogou", e)
        return await search_sogou(query, limit=limit)
