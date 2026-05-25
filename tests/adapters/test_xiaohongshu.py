import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.xiaohongshu import XiaohongshuAdapter


async def test_xhs_search_parses_opencli_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "Claude 4.7 上手 5 分钟入门",
                "url": "https://xiaohongshu.com/discovery/item/abc",
                "author": "AI小白",
                "content": "今天试了一下 Claude 4.7 …",
                "published_at": "2026-05-21T08:00:00Z",
                "like_count": 4200,
                "comment_count": 87,
                "collect_count": 256,
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.xiaohongshu.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda n: "/usr/bin/" + n)

    out = await XiaohongshuAdapter().search("claude", limit=3)
    assert len(out) == 1
    assert out[0].source == "xiaohongshu"
    assert out[0].author == "AI小白"
    assert out[0].engagement.likes == 4200
    assert out[0].engagement.comments == 87
    assert out[0].engagement.shares == 256


async def test_xhs_missing_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable) as exc:
        await XiaohongshuAdapter().search("x")
    assert "opencli" in str(exc.value).lower()


async def test_xhs_is_ready_requires_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda n: "/usr/bin/opencli")
    assert await XiaohongshuAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda n: None)
    assert await XiaohongshuAdapter().is_ready() is False
