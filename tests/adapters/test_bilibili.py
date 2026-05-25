import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.bilibili import BilibiliAdapter


async def test_bilibili_search_parses_agent_reach_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "Claude Code 教程",
                "url": "https://bilibili.com/video/BVxxxx",
                "subtitle": "字幕全文…",
                "uploader": "技术宅",
                "play_count": 88000,
                "like_count": 4500,
                "published_at": "2026-05-10T00:00:00Z",
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0
            async def communicate(self):
                return (fake.encode(), b"")
        return P()

    monkeypatch.setattr("omnireach.adapters.bilibili.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.bilibili.shutil.which", lambda n: "/usr/bin/agent-reach")

    out = await BilibiliAdapter().search("claude", limit=3)
    assert out[0].source == "bilibili"
    assert out[0].engagement.views == 88000
    assert out[0].engagement.likes == 4500


async def test_bilibili_missing_binary(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.bilibili.shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable):
        await BilibiliAdapter().search("x")
