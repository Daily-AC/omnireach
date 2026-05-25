"""HackerNews adapter — talks directly to public JSON API, no upstream needed."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from omnireach.adapters.base import AdapterBase
from omnireach.contract import Engagement, SearchResult

HN_BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsAdapter(AdapterBase):
    name = "hackernews"
    requires: list[str] = []  # zero-config

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        q = query.lower()
        async with httpx.AsyncClient(timeout=15.0) as client:
            top = (await client.get(f"{HN_BASE}/topstories.json")).json()
            top_ids = top[:200]  # widen pool, filter client-side

            async def fetch(item_id: int) -> dict | None:
                try:
                    return (await client.get(f"{HN_BASE}/item/{item_id}.json")).json()
                except Exception:
                    return None

            items = await asyncio.gather(*[fetch(i) for i in top_ids])

        matches: list[SearchResult] = []
        for it in items:
            if not it or it.get("type") != "story":
                continue
            title = it.get("title") or ""
            if q not in title.lower():
                continue
            ts = datetime.fromtimestamp(it.get("time", 0), tz=timezone.utc).isoformat()
            matches.append(
                SearchResult(
                    source="hackernews",
                    adapter="builtin",
                    title=title,
                    url=it.get("url") or f"https://news.ycombinator.com/item?id={it['id']}",
                    content="",
                    author=it.get("by"),
                    ts=ts,
                    score=min(1.0, (it.get("score") or 0) / 500.0),
                    engagement=Engagement(
                        likes=it.get("score"),
                        comments=it.get("descendants"),
                    ),
                    raw=it,
                )
            )
            if len(matches) >= limit:
                break
        return matches
