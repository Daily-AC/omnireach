import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.reddit import RedditAdapter


# OpenCLI v1.8.6 `reddit search` shape observed in a real run on 2026-07-10.
_REAL_OPENCLI_ITEM = {
    "id": "1u6g6tn",
    "title": "I think Claude Code saved my life.",
    "subreddit": "r/ClaudeCode",
    "author": "TheComplicatedMan",
    "score": 561,
    "comments": 169,
    "url": (
        "https://www.reddit.com/r/ClaudeCode/comments/1u6g6tn/"
        "i_think_claude_code_saved_my_life/"
    ),
    "created_utc": 1781529030,
    "selftext": "I was at the prompt working, but did not feel well.",
}


async def test_is_ready_requires_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.reddit.shutil.which", lambda b: "/bin/opencli")
    assert await RedditAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.reddit.shutil.which", lambda b: None)
    assert await RedditAdapter().is_ready() is False


async def test_search_parses_real_opencli_shape(monkeypatch):
    captured: list[str] = []

    async def fake_exec(*args, **kwargs):
        captured.extend(args)

        class P:
            returncode = 0

            async def communicate(self):
                return json.dumps([_REAL_OPENCLI_ITEM]).encode(), b""

        return P()

    monkeypatch.setattr("omnireach.adapters._opencli.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.reddit.shutil.which", lambda b: "/bin/opencli")

    out = await RedditAdapter().search("Claude Code", limit=5)

    assert len(out) == 1
    assert out[0].source == "reddit"
    assert out[0].adapter == "opencli"
    assert out[0].title == "I think Claude Code saved my life."
    assert out[0].url == _REAL_OPENCLI_ITEM["url"]
    assert out[0].content == "I was at the prompt working, but did not feel well."
    assert out[0].author == "TheComplicatedMan"
    assert out[0].engagement.likes == 561
    assert out[0].engagement.comments == 169
    assert out[0].ts == "2026-06-15T13:10:30+00:00"
    assert captured[:4] == ["opencli", "reddit", "search", "Claude Code"]
    assert captured[captured.index("--limit") + 1] == "5"
    assert captured[captured.index("--window") + 1] == "background"
    assert captured[captured.index("--site-session") + 1] == "ephemeral"
    assert captured[captured.index("--keep-tab") + 1] == "false"


async def test_search_raises_when_opencli_missing(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.reddit.shutil.which", lambda b: None)
    with pytest.raises(AdapterUnavailable, match="opencli"):
        await RedditAdapter().search("q")
