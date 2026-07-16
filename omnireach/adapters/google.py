"""Google Search adapter backed by the native Chrome or OpenCLI bridge."""

from __future__ import annotations

import shutil
from urllib.parse import urlparse

from omnireach.adapters.base import AdapterBase
from omnireach.bridge_install import bridge_configured
from omnireach.browser_transport import run_browser_json
from omnireach.contract import SearchResult


def _is_external_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class GoogleAdapter(AdapterBase):
    name = "google"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bridge_configured() or shutil.which("opencli") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        command_result = await run_browser_json(
            "google",
            "search",
            {"query": query, "limit": limit},
            ("google", "search", query, "--limit", str(limit)),
        )
        results: list[SearchResult] = []
        for item in command_result.items:
            url = item.get("url")
            if not _is_external_http_url(url):
                continue
            results.append(
                SearchResult(
                    source="google",
                    adapter=command_result.adapter,
                    title=str(item.get("title") or ""),
                    url=str(url),
                    content=str(item.get("snippet") or ""),
                    score=0.5,
                    raw=item,
                )
            )
            if len(results) >= limit:
                break
        return results
