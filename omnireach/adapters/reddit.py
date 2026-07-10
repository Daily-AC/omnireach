"""Reddit adapter backed by OpenCLI's Chrome bridge."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone

from omnireach.adapters._opencli import run_opencli_json
from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


def _unix_to_iso(ts: float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class RedditAdapter(AdapterBase):
    name = "reddit"
    requires = ["opencli"]

    async def is_ready(self) -> bool:
        return shutil.which("opencli") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("opencli"):
            raise AdapterUnavailable(
                "reddit", "opencli not installed", hint="omnireach setup reddit"
            )

        items = await run_opencli_json(
            "reddit", "reddit", "search", query, "--limit", str(limit)
        )

        results: list[SearchResult] = []
        for item in items[:limit]:
            results.append(SearchResult(
                source="reddit",
                adapter="opencli",
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
