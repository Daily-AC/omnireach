"""抖音 (Douyin) adapter — shells out to OpenCLI's logged-in Chrome session.

Requires the `opencli` binary on PATH plus a Chrome profile logged into
www.douyin.com. The wizard (omnireach setup douyin) walks the user through the
Chrome extension install + douyin login.

Note: `plays`/`comments`/`shares` are normalized zero→None because the douyin
search card markup only surfaces `likes`. Treating zero as "unknown" lets
downstream Agents distinguish unrendered counters from a video that really
has zero engagement. Upstream (OpenCLI PR #1759, currently in Daily-AC fork)
returns 0 for these fields — see PR description for follow-up via aweme detail.
"""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


class DouyinAdapter(AdapterBase):
    name = "douyin"
    requires = ["opencli"]

    async def is_ready(self) -> bool:
        return all(shutil.which(b) is not None for b in self.requires)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("opencli"):
            raise AdapterUnavailable(
                "douyin", "opencli not installed", hint="omnireach setup douyin"
            )

        proc = await asyncio.create_subprocess_exec(
            "opencli", "douyin", "search", "--format", "json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("douyin", err.decode().strip() or "opencli douyin search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("douyin", f"opencli returned non-JSON: {e}")

        items = data if isinstance(data, list) else data.get("results", [])

        results: list[SearchResult] = []
        for item in items[:limit]:
            desc = item.get("desc") or item.get("description") or ""
            title = (desc[:80] + "…") if len(desc) > 80 else desc
            results.append(
                SearchResult(
                    source="douyin",
                    adapter="opencli",
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
