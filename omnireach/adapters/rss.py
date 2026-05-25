"""RSS adapter — Python feedparser. Query MUST be a URL."""

from __future__ import annotations

import asyncio
import re
from email.utils import parsedate_to_datetime

import feedparser

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult

URL_RE = re.compile(r"^(https?|file)://", re.IGNORECASE)


def _parse_ts(entry) -> str | None:
    for field in ("published", "updated", "created"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw).isoformat()
            except (TypeError, ValueError):
                continue
    return None


class RssAdapter(AdapterBase):
    name = "rss"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not URL_RE.match(query.strip()):
            raise AdapterUnavailable(
                "rss", "rss source requires a URL as query",
                hint="omnireach 'https://example.com/feed.xml'",
            )
        feed = await asyncio.to_thread(feedparser.parse, query)
        if feed.bozo and not feed.entries:
            raise AdapterUnavailable("rss", f"feed parse failed: {feed.bozo_exception}")
        results: list[SearchResult] = []
        for entry in feed.entries[:limit]:
            results.append(SearchResult(
                source="rss",
                adapter="feedparser",
                title=entry.get("title") or "",
                url=entry.get("link") or "",
                content=(entry.get("summary") or entry.get("description") or "")[:500],
                author=entry.get("author"),
                ts=_parse_ts(entry),
                raw=dict(entry),
            ))
        return results
