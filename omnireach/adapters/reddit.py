"""Reddit adapter — shells out to rdt-cli."""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timezone

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


def _unix_to_iso(ts: float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class RedditAdapter(AdapterBase):
    name = "reddit"
    requires = ["rdt-cli"]

    async def is_ready(self) -> bool:
        return shutil.which("rdt-cli") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("rdt-cli"):
            raise AdapterUnavailable(
                "reddit", "rdt-cli not installed", hint="omnireach setup reddit"
            )
        proc = await asyncio.create_subprocess_exec(
            "rdt-cli", "search", query, "--json", "--limit", str(limit),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode().strip()
            if "login" in err.lower():
                raise AdapterUnavailable(
                    "reddit", "未登录, 运行 `rdt login` 完成 OAuth", hint="rdt login"
                )
            raise AdapterUnavailable("reddit", err or "rdt-cli failed")
        try:
            data = json.loads(stdout.decode() or "{}")
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("reddit", f"non-JSON from rdt-cli: {e}")
        results: list[SearchResult] = []
        for hit in data.get("results", [])[:limit]:
            permalink = hit.get("permalink") or ""
            url = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else permalink
            results.append(SearchResult(
                source="reddit",
                adapter="rdt-cli",
                title=hit.get("title") or "",
                url=url,
                content=hit.get("selftext") or "",
                author=hit.get("author"),
                ts=_unix_to_iso(hit.get("created_utc")),
                engagement=Engagement(
                    likes=hit.get("score"),
                    comments=hit.get("num_comments"),
                ),
                raw=hit,
            ))
        return results
