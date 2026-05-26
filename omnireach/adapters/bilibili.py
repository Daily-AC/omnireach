"""B站 (Bilibili) adapter — Exa primary (paid), Bilibili API fallback (free, v0.9)."""

from __future__ import annotations
import logging
import os

import httpx

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.adapters._bilibili_api import search_bilibili
from omnireach.contract import SearchResult

log = logging.getLogger(__name__)

EXA_URL = "https://api.exa.ai/search"
DOMAINS = ["bilibili.com", "www.bilibili.com"]


async def _search_exa(query: str, *, limit: int) -> list[SearchResult]:
    """Exa-backed search path — primary (paid)."""
    key = os.environ.get("EXA_API_KEY")
    if not key:
        raise AdapterUnavailable("bilibili:exa", "EXA_API_KEY 未设置", hint="omnireach setup bilibili")
    headers = {"x-api-key": key, "Content-Type": "application/json"}
    # v0.9.1: see exa.py for rationale on contents.text.maxCharacters=2000.
    body = {"query": query, "numResults": limit, "type": "auto",
            "includeDomains": DOMAINS,
            "contents": {"text": {"maxCharacters": 2000}}}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(EXA_URL, json=body, headers=headers)
        except httpx.HTTPError as e:
            raise AdapterUnavailable("bilibili:exa", f"http error: {e}") from e
    if resp.status_code == 401:
        raise AdapterUnavailable("bilibili:exa", "API Key 无效 (401)")
    if resp.status_code == 429:
        raise AdapterUnavailable("bilibili:exa", "rate limited (429)")
    if resp.status_code >= 500:
        raise AdapterUnavailable("bilibili:exa", f"upstream {resp.status_code}")
    data = resp.json()
    results: list[SearchResult] = []
    for hit in data.get("results", [])[:limit]:
        results.append(SearchResult(
            source="bilibili",
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


class BilibiliAdapter(AdapterBase):
    name = "bilibili"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        # Either backend works → adapter is always ready
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        # Priority: Exa (if EXA_API_KEY set) > Bilibili API (free fallback)
        if os.environ.get("EXA_API_KEY"):
            try:
                return await _search_exa(query, limit=limit)
            except AdapterUnavailable as e:
                log.warning("bilibili: Exa unavailable (%s), falling back to Bilibili API", e)
        return await search_bilibili(query, limit=limit)
