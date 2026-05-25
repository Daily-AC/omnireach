import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.wechat import WeChatAdapter


async def test_wechat_search_parses_agent_reach_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "Claude 4.7 评测",
                "url": "https://mp.weixin.qq.com/s/xxx",
                "content_markdown": "# Claude 4.7…",
                "account": "AI 前线",
                "published_at": "2026-05-20T00:00:00Z",
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0
            async def communicate(self):
                return (fake.encode(), b"")
        return P()

    monkeypatch.setattr("omnireach.adapters.wechat.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.wechat.shutil.which", lambda n: "/usr/bin/agent-reach")

    out = await WeChatAdapter().search("claude", limit=3)
    assert out[0].source == "wechat"
    assert out[0].author == "AI 前线"


async def test_wechat_missing_binary(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.wechat.shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable):
        await WeChatAdapter().search("x")
