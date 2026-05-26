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


def _parse_likes(v: object) -> int | None:
    """OpenCLI returns likes as a string ('102', '1593'). Parse to int or None."""
    if v is None:
        return None
    try:
        return int(str(v))
    except (TypeError, ValueError):
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

        proc = await asyncio.create_subprocess_exec(
            "opencli", "xiaohongshu", "search", "--format", "json", "--limit", str(limit), query,
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

        # opencli v1.7.22 returns a JSON array directly. Older shapes used {"results": [...]}.
        items = data if isinstance(data, list) else data.get("results", [])

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
