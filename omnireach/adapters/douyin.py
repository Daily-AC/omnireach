"""抖音 (Douyin) adapter backed by the user's logged-in Chrome session.

The native Omnireach bridge is preferred. OpenCLI remains a compatibility
fallback when the bridge is not installed or its extension is disconnected.

Note: `plays`/`comments`/`shares` are normalized zero→None because the douyin
search card markup only surfaces `likes`. Treating zero as "unknown" lets
downstream Agents distinguish unrendered counters from a video that really
has zero engagement. Upstream (OpenCLI PR #1759, currently in Daily-AC fork)
returns 0 for these fields — see PR description for follow-up via aweme detail.
"""

from __future__ import annotations

import shutil

from omnireach.adapters.base import AdapterBase
from omnireach.bridge_install import bridge_configured
from omnireach.browser_transport import run_browser_json
from omnireach.contract import Engagement, SearchResult


class DouyinAdapter(AdapterBase):
    name = "douyin"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bridge_configured() or shutil.which("opencli") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        command_result = await run_browser_json(
            "douyin",
            "search",
            {"query": query, "limit": limit},
            ("douyin", "search", "--limit", str(limit), query),
        )

        results: list[SearchResult] = []
        for item in command_result.items[:limit]:
            desc = item.get("desc") or item.get("description") or ""
            title = (desc[:80] + "…") if len(desc) > 80 else desc
            results.append(
                SearchResult(
                    source="douyin",
                    adapter=command_result.adapter,
                    title=title,
                    url=item.get("url", ""),
                    content=desc,
                    author=item.get("author"),
                    ts=None,
                    score=0.5,
                    engagement=Engagement(
                        views=item.get("plays") or None,
                        likes=item.get("likes") or None,
                        comments=item.get("comments") or None,
                        shares=item.get("shares") or None,
                    ),
                    raw=item,
                )
            )
        return results
