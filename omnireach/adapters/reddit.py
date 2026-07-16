"""Reddit adapter backed by the native Chrome or OpenCLI bridge."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone

from omnireach.adapters.base import AdapterBase
from omnireach.bridge_install import bridge_configured
from omnireach.browser_transport import run_browser_json
from omnireach.contract import Engagement, SearchResult


def _unix_to_iso(ts: float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class RedditAdapter(AdapterBase):
    name = "reddit"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bridge_configured() or shutil.which("opencli") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        command_result = await run_browser_json(
            "reddit",
            "search",
            {"query": query, "limit": limit},
            ("reddit", "search", query, "--limit", str(limit)),
        )

        results: list[SearchResult] = []
        for item in command_result.items[:limit]:
            results.append(SearchResult(
                source="reddit",
                adapter=command_result.adapter,
                title=item.get("title") or "",
                url=item.get("url") or "",
                content=item.get("selftext") or "",
                author=item.get("author"),
                ts=_unix_to_iso(item.get("created_utc")),
                engagement=Engagement(
                    likes=item.get("score"),
                    comments=item.get("comments"),
                ),
                raw=item,
            ))
        return results
