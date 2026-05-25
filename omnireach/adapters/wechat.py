"""WeChat 公众号 adapter — shells out to agent-reach."""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult


class WeChatAdapter(AdapterBase):
    name = "wechat"
    requires = ["agent-reach"]

    async def is_ready(self) -> bool:
        return shutil.which("agent-reach") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("agent-reach"):
            raise AdapterUnavailable(
                "wechat", "agent-reach not installed", hint="omnireach init  (会自动 pipx install)"
            )

        proc = await asyncio.create_subprocess_exec(
            "agent-reach", "wechat", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("wechat", err.decode().strip() or "agent-reach wechat search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("wechat", f"agent-reach returned non-JSON: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    source="wechat",
                    adapter="agent-reach",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content_markdown", "") or item.get("content", ""),
                    author=item.get("account"),
                    ts=item.get("published_at"),
                    score=0.5,
                    raw=item,
                )
            )
        return results
