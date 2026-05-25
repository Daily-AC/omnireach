"""YouTube adapter — shells out to yt-dlp."""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timezone

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


def _unix_to_iso(ts: int | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class YouTubeAdapter(AdapterBase):
    name = "youtube"
    requires = ["yt-dlp"]

    async def is_ready(self) -> bool:
        return shutil.which("yt-dlp") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("yt-dlp"):
            raise AdapterUnavailable(
                "youtube", "yt-dlp not installed", hint="omnireach setup youtube"
            )
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            f"ytsearch{limit}:{query}",
            "--flat-playlist",
            "--dump-json",
            "--no-warnings",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("youtube", stderr.decode().strip() or "yt-dlp failed")
        results: list[SearchResult] = []
        for line in stdout.decode().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            results.append(
                SearchResult(
                    source="youtube",
                    adapter="yt-dlp",
                    title=entry.get("title") or "",
                    url=entry.get("url") or entry.get("webpage_url") or "",
                    content="",
                    author=entry.get("uploader"),
                    ts=_unix_to_iso(entry.get("timestamp")),
                    engagement=Engagement(views=entry.get("view_count")),
                    raw=entry,
                )
            )
        return results
