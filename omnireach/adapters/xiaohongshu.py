"""小红书 (Xiaohongshu) adapter — shells out to OpenCLI's logged-in Chrome session.

Requires the `opencli` binary on PATH plus a Chrome profile logged into
xiaohongshu.com. The wizard (omnireach setup xiaohongshu) walks the user
through the Chrome extension install + xiaohongshu login.
"""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


class XiaohongshuAdapter(AdapterBase):
    name = "xiaohongshu"
    requires = ["opencli"]

    async def is_ready(self) -> bool:
        return shutil.which("opencli") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("opencli"):
            raise AdapterUnavailable(
                "xiaohongshu", "opencli not installed", hint="omnireach setup xiaohongshu"
            )

        proc = await asyncio.create_subprocess_exec(
            "opencli", "xiaohongshu", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("xiaohongshu", err.decode().strip() or "opencli xiaohongshu search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("xiaohongshu", f"opencli returned non-JSON: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
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
                        likes=item.get("like_count"),
                        comments=item.get("comment_count"),
                        shares=item.get("collect_count"),
                    ),
                    raw=item,
                )
            )
        return results
