import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.douyin import DouyinAdapter


async def test_douyin_search_parses_opencli_json_array(monkeypatch):
    """Field shape captured from a real `opencli douyin search "claude code" --format json`
    against Daily-AC/OpenCLI fork main (commit d76c4d99) on 2026-05-26.
    """
    fake = json.dumps([
        {
            "rank": 1,
            "desc": "全网最全！60分钟全面掌握Claude Code～ #AI #ClaudeCode",
            "author": "秋芝2046",
            "url": "https://www.douyin.com/video/7636497165430394162",
            "plays": 0,
            "likes": 40000,
            "comments": 0,
            "shares": 0,
        }
    ])

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters._opencli.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.douyin.shutil.which", lambda n: "/usr/bin/" + n)

    out = await DouyinAdapter().search("claude code", limit=3)
    assert len(out) == 1
    assert out[0].source == "douyin"
    assert out[0].author == "秋芝2046"
    assert out[0].engagement.likes == 40000
    # zero→None normalization: search card only surfaces likes
    assert out[0].engagement.views is None
    assert out[0].engagement.comments is None
    assert out[0].engagement.shares is None
    assert out[0].ts is None


async def test_douyin_search_invokes_opencli_with_format_json(monkeypatch):
    captured_argv: list = []

    async def fake_exec(*args, **kwargs):
        captured_argv.extend(args)

        class P:
            returncode = 0

            async def communicate(self):
                return (b"[]", b"")

        return P()

    monkeypatch.setattr("omnireach.adapters._opencli.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.douyin.shutil.which", lambda n: "/usr/bin/" + n)

    await DouyinAdapter().search("claude", limit=5)

    assert "--json" not in captured_argv
    assert "--format" in captured_argv
    assert captured_argv[captured_argv.index("--format") + 1] == "json"
    assert "opencli" in captured_argv
    assert "douyin" in captured_argv
    assert "search" in captured_argv
    assert "claude" in captured_argv


async def test_douyin_search_zero_likes_also_normalized_to_none(monkeypatch):
    """If an actual video has 0 real likes (very rare), normalize to None too —
    we can't distinguish 'unknown' from 'truly zero' without an extra detail call."""
    fake = json.dumps([{"rank": 1, "desc": "x", "author": "u", "url": "https://www.douyin.com/video/1",
                       "plays": 0, "likes": 0, "comments": 0, "shares": 0}])

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters._opencli.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.douyin.shutil.which", lambda n: "/usr/bin/" + n)

    out = await DouyinAdapter().search("x")
    assert out[0].engagement.likes is None  # 0 → None is the chosen trade-off


async def test_douyin_missing_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.douyin.shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable) as exc:
        await DouyinAdapter().search("x")
    assert "opencli" in str(exc.value).lower()


async def test_douyin_is_ready_requires_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.douyin.shutil.which", lambda n: "/usr/bin/opencli")
    assert await DouyinAdapter().is_ready() is True
    monkeypatch.setattr("omnireach.adapters.douyin.shutil.which", lambda n: None)
    assert await DouyinAdapter().is_ready() is False
