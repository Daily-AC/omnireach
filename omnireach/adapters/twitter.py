"""Twitter / X adapter — shells out to OpenCLI, which uses a logged-in Chrome session.

Requires the `opencli` binary on PATH. The user must have:
  1. installed the OpenCLI Chrome Bridge extension from chrome.google.com
  2. logged into twitter.com in that Chrome profile

The wizard (omnireach setup twitter) walks the user through both manual steps
with `opencli doctor` and `opencli twitter state` as verify commands.
"""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


class TwitterAdapter(AdapterBase):
    name = "twitter"
    requires = ["opencli"]

    async def is_ready(self) -> bool:
        return all(shutil.which(b) is not None for b in self.requires)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("opencli"):
            raise AdapterUnavailable(
                "twitter", "opencli not installed", hint="omnireach setup twitter"
            )

        proc = await asyncio.create_subprocess_exec(
            "opencli", "twitter", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("twitter", err.decode().strip() or "opencli twitter search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("twitter", f"opencli returned non-JSON: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            text = item.get("text", "") or ""
            title = (text[:80] + "…") if len(text) > 80 else text
            results.append(
                SearchResult(
                    source="twitter",
                    adapter="opencli",
                    title=title,
                    url=item.get("url", ""),
                    content=text,
                    author=item.get("author"),
                    ts=item.get("created_at"),
                    score=0.5,
                    engagement=Engagement(
                        likes=item.get("like_count"),
                        shares=item.get("retweet_count"),
                        comments=item.get("reply_count"),
                    ),
                    raw=item,
                )
            )
        return results
