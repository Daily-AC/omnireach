import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.youtube import YouTubeAdapter


async def test_youtube_search_parses_agent_reach_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "Claude Code intro",
                "url": "https://youtube.com/watch?v=abc",
                "channel": "Anthropic",
                "transcript": "Welcome…",
                "published_at": "2026-05-01T00:00:00Z",
                "views": 12345,
                "likes": 678,
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0
            async def communicate(self):
                return (fake.encode(), b"")
        return P()

    monkeypatch.setattr("omnireach.adapters.youtube.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.youtube.shutil.which", lambda n: "/usr/bin/agent-reach")

    out = await YouTubeAdapter().search("claude code", limit=3)
    assert out[0].source == "youtube"
    assert out[0].author == "Anthropic"
    assert out[0].engagement.likes == 678
    assert out[0].engagement.views == 12345


async def test_youtube_missing_binary(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.youtube.shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable):
        await YouTubeAdapter().search("x")
