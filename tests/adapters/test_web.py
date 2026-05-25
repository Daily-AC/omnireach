import asyncio
import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.web import WebSearchAdapter


async def test_web_search_parses_agent_reach_json(monkeypatch):
    fake_output = json.dumps({
        "results": [
            {
                "title": "claude docs",
                "url": "https://docs.anthropic.com",
                "content": "Claude is...",
                "published_at": "2026-05-01T00:00:00Z",
            }
        ]
    })

    async def fake_subprocess_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake_output.encode(), b"")

        return P()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess_exec)
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/agent-reach")

    a = WebSearchAdapter()
    out = await a.search("claude", limit=3)
    assert len(out) == 1
    assert out[0].source == "web"
    assert out[0].url == "https://docs.anthropic.com"


async def test_web_missing_binary_raises_unavailable(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    a = WebSearchAdapter()
    with pytest.raises(AdapterUnavailable):
        await a.search("claude")


async def test_web_is_ready_checks_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/agent-reach")
    a = WebSearchAdapter()
    assert await a.is_ready() is True
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert await a.is_ready() is False
