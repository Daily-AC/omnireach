"""Reddit adapter — shells out to agent-reach (which uses rdt-cli under the hood).

Unlike the other agent-reach adapters, Reddit requires BOTH `agent-reach` AND
`rdt-cli` binaries on PATH, since agent-reach delegates Reddit calls to rdt-cli.
"""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


class RedditAdapter(AdapterBase):
    name = "reddit"
    requires = ["agent-reach", "rdt-cli"]

    async def is_ready(self) -> bool:
        return all(shutil.which(b) is not None for b in self.requires)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("agent-reach"):
            raise AdapterUnavailable(
                "reddit", "agent-reach not installed", hint="omnireach setup reddit"
            )
        if not shutil.which("rdt-cli"):
            raise AdapterUnavailable(
                "reddit", "rdt-cli not installed", hint="omnireach setup reddit"
            )

        proc = await asyncio.create_subprocess_exec(
            "agent-reach", "reddit", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("reddit", err.decode().strip() or "agent-reach reddit search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("reddit", f"agent-reach returned non-JSON: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    source="reddit",
                    adapter="agent-reach",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("selftext", "") or item.get("body", ""),
                    author=item.get("author"),
                    ts=item.get("created_utc") or item.get("created_at"),
                    score=0.5,
                    engagement=Engagement(
                        likes=item.get("score"),
                        comments=item.get("num_comments"),
                    ),
                    raw=item,
                )
            )
        return results
