"""TikTok adapter backed by the native Chrome or OpenCLI bridge."""

from __future__ import annotations

import shutil

from omnireach.adapters.base import AdapterBase
from omnireach.bridge_install import bridge_configured
from omnireach.browser_transport import run_browser_json
from omnireach.contract import Engagement, SearchResult


class TikTokAdapter(AdapterBase):
    name = "tiktok"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bridge_configured() or shutil.which("opencli") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        command_result = await run_browser_json(
            "tiktok",
            "search",
            {"query": query, "limit": limit},
            ("tiktok", "search", "--limit", str(limit), query),
        )

        results: list[SearchResult] = []
        for item in command_result.items[:limit]:
            desc = item.get("desc") or item.get("description") or item.get("title") or ""
            title = (desc[:80] + "…") if len(desc) > 80 else desc
            # OpenCLI v1.7.22 tiktok search returns: author, comments, desc, likes,
            # plays, rank, shares, url. No timestamp field.
            results.append(
                SearchResult(
                    source="tiktok",
                    adapter=command_result.adapter,
                    title=title,
                    url=item.get("url", ""),
                    content=desc,
                    author=item.get("author"),
                    ts=item.get("created_at") or item.get("published_at"),
                    score=0.5,
                    engagement=Engagement(
                        views=item.get("plays") or item.get("play_count") or item.get("view_count"),
                        likes=item.get("likes") or item.get("like_count") or item.get("digg_count"),
                        comments=item.get("comments") or item.get("comment_count"),
                        shares=item.get("shares") or item.get("share_count"),
                    ),
                    raw=item,
                )
            )
        return results
