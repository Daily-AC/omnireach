"""Perplexity Sonar booster (paid)."""

from __future__ import annotations

import os

import httpx

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult

PPLX_URL = "https://api.perplexity.ai/chat/completions"
PPLX_MODEL = "sonar-pro"


class PerplexityAdapter(AdapterBase):
    name = "perplexity"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bool(os.environ.get("PERPLEXITY_API_KEY"))

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        key = os.environ.get("PERPLEXITY_API_KEY")
        if not key:
            raise AdapterUnavailable("perplexity", "PERPLEXITY_API_KEY 未设置", hint="omnireach setup perplexity")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {
            "model": PPLX_MODEL,
            "messages": [{"role": "user", "content": query}],
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(PPLX_URL, headers=headers, json=body)
            except httpx.HTTPError as e:
                raise AdapterUnavailable("perplexity", f"http error: {e}") from e
        if resp.status_code == 401:
            raise AdapterUnavailable("perplexity", "API Key 无效 (401)")
        if resp.status_code == 429:
            raise AdapterUnavailable("perplexity", "rate limited (429)")
        if resp.status_code >= 500:
            raise AdapterUnavailable("perplexity", f"upstream {resp.status_code}")
        data = resp.json()
        summary = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        citations = data.get("citations") or []
        results: list[SearchResult] = []
        for i, url in enumerate(citations[:limit]):
            results.append(
                SearchResult(
                    source="perplexity",
                    adapter="perplexity-api",
                    title=f"[{i+1}] {url}",
                    url=url,
                    content=summary if i == 0 else "",
                    cost="paid",
                    raw={"citation_index": i, "summary": summary},
                )
            )
        return results
