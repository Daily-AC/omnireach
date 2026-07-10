"""小红书 (Xiaohongshu) adapter — shells out to OpenCLI's logged-in Chrome session.

Requires the `opencli` binary on PATH plus a Chrome profile logged into
xiaohongshu.com. The wizard (omnireach setup xiaohongshu) walks the user
through the Chrome extension install + xiaohongshu login.
"""

from __future__ import annotations

import re
import shutil
from decimal import Decimal, InvalidOperation

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.adapters._opencli import run_opencli_json
from omnireach.contract import Engagement, SearchResult


def _parse_likes(v: object) -> int | None:
    """Normalize OpenCLI counts such as ``102``, ``1.2万`` or ``1.2k``."""
    if v is None or isinstance(v, bool):
        return None
    match = re.fullmatch(
        r"([0-9]+(?:\.[0-9]+)?)\s*([万亿km]?)\+?",
        str(v).strip().replace(",", "").lower(),
    )
    if match is None:
        return None
    multiplier = {
        "": 1,
        "k": 1_000,
        "m": 1_000_000,
        "万": 10_000,
        "亿": 100_000_000,
    }[match.group(2)]
    try:
        return int(Decimal(match.group(1)) * multiplier)
    except InvalidOperation:
        return None


class XiaohongshuAdapter(AdapterBase):
    name = "xiaohongshu"
    requires = ["opencli"]

    async def is_ready(self) -> bool:
        return all(shutil.which(b) is not None for b in self.requires)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("opencli"):
            raise AdapterUnavailable(
                "xiaohongshu", "opencli not installed", hint="omnireach setup xiaohongshu"
            )

        items = await run_opencli_json(
            "xiaohongshu", "xiaohongshu", "search", "--limit", str(limit), query
        )

        # OpenCLI xhs search keys observed (v0.8.1 hotfix, real E2E 2026-05-27):
        # rank, author, author_url, likes(string), title, url, published_at.
        # body / comment_count / collect_count are NOT exposed in search results,
        # so content stays "" and comments/shares stay None.
        results: list[SearchResult] = []
        for item in items[:limit]:
            results.append(
                SearchResult(
                    source="xiaohongshu",
                    adapter="opencli",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    author=item.get("author"),
                    ts=item.get("published_at"),
                    score=0.5,
                    engagement=Engagement(
                        likes=_parse_likes(item.get("likes")),
                    ),
                    raw=item,
                )
            )
        return results
