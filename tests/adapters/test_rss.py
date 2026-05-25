import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.rss import RSSAdapter


async def test_rss_search_parses_agent_reach_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "Anthropic ships Claude 4.7",
                "url": "https://anthropic.com/blog/4-7",
                "summary": "...",
                "published_at": "2026-05-20T00:00:00Z",
                "feed": "https://anthropic.com/rss",
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0
            async def communicate(self):
                return (fake.encode(), b"")
        return P()

    monkeypatch.setattr("omnireach.adapters.rss.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.rss.shutil.which", lambda n: "/usr/bin/agent-reach")

    out = await RSSAdapter().search("anthropic", limit=3)
    assert out[0].source == "rss"


async def test_rss_missing_binary(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.rss.shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable):
        await RSSAdapter().search("x")
