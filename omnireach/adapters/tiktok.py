"""TikTok adapter — shells out to OpenCLI's logged-in Chrome session.

Requires the `opencli` binary on PATH plus a Chrome profile logged into
tiktok.com. The wizard (omnireach setup tiktok) walks the user through the
Chrome extension install + tiktok login.

Note: this adapter targets TikTok (international, tiktok.com), NOT 抖音 (douyin.com).
For 抖音 see omnireach/adapters/douyin.py once OpenCLI ships douyin search support.
"""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


class TikTokAdapter(AdapterBase):
    name = "tiktok"
    requires = ["opencli"]

    async def is_ready(self) -> bool:
        return all(shutil.which(b) is not None for b in self.requires)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("opencli"):
            raise AdapterUnavailable(
                "tiktok", "opencli not installed", hint="omnireach setup tiktok"
            )

        proc = await asyncio.create_subprocess_exec(
            "opencli", "tiktok", "search", "--format", "json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("tiktok", err.decode().strip() or "opencli tiktok search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("tiktok", f"opencli returned non-JSON: {e}")

        items = data if isinstance(data, list) else data.get("results", [])

        results: list[SearchResult] = []
        for item in items[:limit]:
            desc = item.get("desc") or item.get("description") or item.get("title") or ""
            title = (desc[:80] + "…") if len(desc) > 80 else desc
            # OpenCLI v1.7.22 tiktok search returns: author, comments, desc, likes,
            # plays, rank, shares, url. No timestamp field.
            results.append(
                SearchResult(
                    source="tiktok",
                    adapter="opencli",
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
