"""Google Search adapter backed by OpenCLI's silent Chrome bridge."""

from __future__ import annotations

import shutil
from urllib.parse import urlparse

from omnireach.adapters._opencli import run_opencli_json
from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult


def _is_external_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class GoogleAdapter(AdapterBase):
    name = "google"
    requires = ["opencli"]

    async def is_ready(self) -> bool:
        return shutil.which("opencli") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("opencli"):
            raise AdapterUnavailable(
                "google", "opencli not installed", hint="omnireach setup google"
            )

        items = await run_opencli_json(
            "google", "google", "search", query, "--limit", str(limit)
        )
        results: list[SearchResult] = []
        for item in items:
            url = item.get("url")
            if not _is_external_http_url(url):
                continue
            results.append(
                SearchResult(
                    source="google",
                    adapter="opencli",
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
