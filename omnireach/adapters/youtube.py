"""YouTube adapter — shells out to agent-reach."""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


class YouTubeAdapter(AdapterBase):
    name = "youtube"
    requires = ["agent-reach"]

    async def is_ready(self) -> bool:
        return shutil.which("agent-reach") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("agent-reach"):
            raise AdapterUnavailable(
                "youtube", "agent-reach not installed", hint="omnireach init  (会自动 pipx install)"
            )

        proc = await asyncio.create_subprocess_exec(
            "agent-reach", "youtube", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("youtube", err.decode().strip() or "agent-reach youtube search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("youtube", f"agent-reach returned non-JSON: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    source="youtube",
                    adapter="agent-reach",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("transcript", "") or item.get("description", ""),
                    author=item.get("channel"),
                    ts=item.get("published_at"),
                    score=0.5,
                    engagement=Engagement(
                        likes=item.get("likes"),
                        views=item.get("views"),
                    ),
                    raw=item,
                )
            )
        return results
