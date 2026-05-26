"""Exa Search API booster (paid)."""

from __future__ import annotations

import os

import httpx

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult

EXA_URL = "https://api.exa.ai/search"


class ExaAdapter(AdapterBase):
    name = "exa"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bool(os.environ.get("EXA_API_KEY"))

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        key = os.environ.get("EXA_API_KEY")
        if not key:
            raise AdapterUnavailable("exa", "EXA_API_KEY 未设置", hint="omnireach setup exa")
        headers = {"x-api-key": key, "Content-Type": "application/json"}
        # v0.9.1: ask for text content explicitly. Without `contents`, Exa
        # returns metadata only and result.content stays "" (silently broken
        # since v0.5). maxCharacters=2000 caps per-result text to ~4× the
        # SearchResult snippet limit, avoiding envelope-size blow-up on
        # multi-result queries while giving downstream enough material.
        body = {"query": query, "numResults": limit, "type": "auto",
                "contents": {"text": {"maxCharacters": 2000}}}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(EXA_URL, json=body, headers=headers)
            except httpx.HTTPError as e:
                raise AdapterUnavailable("exa", f"http error: {e}") from e
        if resp.status_code == 401:
            raise AdapterUnavailable("exa", "API Key 无效 (401)")
        if resp.status_code == 429:
            raise AdapterUnavailable("exa", "rate limited (429)")
        if resp.status_code >= 500:
            raise AdapterUnavailable("exa", f"upstream {resp.status_code}")
        data = resp.json()
        results: list[SearchResult] = []
        for hit in data.get("results", [])[:limit]:
            results.append(SearchResult(
                source="exa",
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
