"""HackerNews adapter — talks directly to Algolia HN Search API, no upstream needed."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from omnireach.adapters.base import AdapterBase
from omnireach.contract import Engagement, SearchResult

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"


class HackerNewsAdapter(AdapterBase):
    name = "hackernews"
    requires: list[str] = []  # zero-config

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        params = {"query": query, "tags": "story", "hitsPerPage": limit}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(ALGOLIA_URL, params=params)
            data = resp.json()

        results: list[SearchResult] = []
        for hit in data.get("hits", [])[:limit]:
            object_id = hit.get("objectID") or ""
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
            created_i = hit.get("created_at_i") or 0
            ts = datetime.fromtimestamp(created_i, tz=timezone.utc).isoformat() if created_i else None
            points = hit.get("points") or 0
            results.append(
                SearchResult(
                    source="hackernews",
                    adapter="builtin",
                    title=hit.get("title") or "",
                    url=url,
                    content="",
                    author=hit.get("author"),
                    ts=ts,
                    score=min(1.0, points / 500.0),
                    engagement=Engagement(
                        likes=points,
                        comments=hit.get("num_comments"),
                    ),
                    raw=hit,
                )
            )
        return results
