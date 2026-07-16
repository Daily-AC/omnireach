"""Twitter / X adapter backed by the native Chrome or OpenCLI bridge."""

from __future__ import annotations

import shutil

from omnireach.adapters.base import AdapterBase
from omnireach.bridge_install import bridge_configured
from omnireach.browser_transport import run_browser_json
from omnireach.contract import Engagement, SearchResult


def _int_or_none(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        return None


class TwitterAdapter(AdapterBase):
    name = "twitter"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bridge_configured() or shutil.which("opencli") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        command_result = await run_browser_json(
            "twitter",
            "search",
            {"query": query, "limit": limit},
            ("twitter", "search", "--limit", str(limit), query),
        )

        results: list[SearchResult] = []
        for item in command_result.items[:limit]:
            text = item.get("text", "") or ""
            title = (text[:80] + "…") if len(text) > 80 else text
            results.append(
                SearchResult(
                    source="twitter",
                    adapter=command_result.adapter,
                    title=title,
                    url=item.get("url", ""),
                    content=text,
                    author=item.get("author"),
                    ts=item.get("created_at"),
                    score=0.5,
                    engagement=Engagement(
                        likes=_int_or_none(item.get("likes", item.get("like_count"))),
                        shares=_int_or_none(item.get("retweets", item.get("retweet_count"))),
                        comments=_int_or_none(item.get("replies", item.get("reply_count"))),
                        views=_int_or_none(item.get("views")),
                    ),
                    raw=item,
                )
            )
        return results
