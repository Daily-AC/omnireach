"""抖音 (Douyin) adapter backed by the user's logged-in Chrome session.

The native Omnireach bridge is preferred. OpenCLI remains a compatibility
fallback when the bridge is not installed or its extension is disconnected.

Two dimensions, two data paths:

* `search` scrapes keyword-result cards, so `plays`/`comments`/`shares` are
  normalized zero→None — the card markup only renders `likes`, and treating
  zero as "unknown" lets Agents tell an unrendered counter apart from a video
  that really has none.
* `author` calls Douyin's own `aweme/v1/web/aweme/post/` JSON API from the
  logged-in page context, which needs no request signing and returns exact
  counters, so nothing there is guessed. Only the native bridge can reach it;
  `opencli douyin user-videos` caps at 20 results and pins `max_cursor`, so it
  cannot page a catalog.
"""

from __future__ import annotations

import shutil
from typing import Any, Literal

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.bridge_install import bridge_configured
from omnireach.browser_transport import run_browser_json
from omnireach.contract import AuthorIdentity, Engagement, SearchResult


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

    async def author(
        self,
        handle: str,
        *,
        limit: int = 20,
        order: Literal["recent", "likes"] = "recent",
        include_media_urls: bool = False,
        timeout: float = 180.0,
    ) -> tuple[AuthorIdentity, list[SearchResult], dict[str, Any]]:
        """Return one creator's own works, newest-first or by likes."""
        command_result = await run_browser_json(
            "douyin",
            "author",
            {
                "handle": handle,
                "limit": limit,
                "order": order,
                "include_media_urls": include_media_urls,
                # Leave the bridge a margin so the extension returns what it has
                # instead of the bridge giving up on it with nothing.
                "budget_ms": max(5000, int(timeout * 1000 * 0.85)),
            },
            result_timeout=timeout,
        )
        if not command_result.items:
            raise AdapterUnavailable(
                "douyin", "the Chrome bridge returned no creator catalog envelope"
            )
        catalog = command_result.items[0]
        works = catalog.get("works")
        if not isinstance(works, list):
            raise AdapterUnavailable(
                "douyin", "the Chrome bridge returned a malformed creator catalog"
            )
        sec_uid = str(catalog.get("sec_uid") or "")
        identity = AuthorIdentity(
            source="douyin",
            handle=handle,
            id=sec_uid,
            name=str(catalog.get("nickname") or ""),
            url=f"https://www.douyin.com/user/{sec_uid}" if sec_uid else "",
            followers=int(catalog.get("followers") or 0) or None,
            resolved_from=(
                "url" if catalog.get("resolved_from") == "url" else "search"
            ),
        )
        total = len(works)
        results = [
            SearchResult(
                source="douyin",
                adapter=command_result.adapter,
                title=self._title(str(item.get("desc") or "")),
                url=str(item.get("url") or ""),
                content=str(item.get("desc") or ""),
                author=item.get("author") or identity.name or None,
                ts=str(item.get("created_at") or "") or None,
                # Rank carried as a score so the chosen order survives any
                # downstream re-sort; the list itself is already ordered.
                score=round(1 - index / total, 4) if total else 0.0,
                engagement=Engagement(
                    views=item.get("plays") or None,
                    likes=item.get("likes") or None,
                    comments=item.get("comments") or None,
                    shares=item.get("shares") or None,
                    collects=item.get("collects") or None,
                ),
                raw=item,
            )
            for index, item in enumerate(works)
        ]
        stats = {
            "order": "likes" if catalog.get("order") == "likes" else "recent",
            "scanned": int(catalog.get("scanned") or 0),
            "complete": bool(catalog.get("complete")),
            "pages": int(catalog.get("pages") or 0),
        }
        return identity, results, stats

    @staticmethod
    def _title(desc: str) -> str:
        return (desc[:80] + "…") if len(desc) > 80 else desc
