"""Twitter / X adapter — shells out to OpenCLI, which uses a logged-in Chrome session.

Requires the `opencli` binary on PATH. The user must have:
  1. installed the OpenCLI Chrome Bridge extension from chrome.google.com
  2. logged into twitter.com in that Chrome profile

The wizard (omnireach setup twitter) walks the user through both manual steps
with `opencli doctor` and `opencli twitter state` as verify commands.
"""

from __future__ import annotations

import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.adapters._opencli import run_opencli_json
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
    requires = ["opencli"]

    async def is_ready(self) -> bool:
        return all(shutil.which(b) is not None for b in self.requires)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("opencli"):
            raise AdapterUnavailable(
                "twitter", "opencli not installed", hint="omnireach setup twitter"
            )

        items = await run_opencli_json(
            "twitter", "twitter", "search", "--limit", str(limit), query
        )

        results: list[SearchResult] = []
        for item in items[:limit]:
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
                        likes=_int_or_none(item.get("likes", item.get("like_count"))),
                        shares=_int_or_none(item.get("retweets", item.get("retweet_count"))),
                        comments=_int_or_none(item.get("replies", item.get("reply_count"))),
                        views=_int_or_none(item.get("views")),
                    ),
                    raw=item,
                )
            )
        return results
