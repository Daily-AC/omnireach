import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.xiaohongshu import XiaohongshuAdapter


async def test_xhs_search_parses_opencli_json_array(monkeypatch):
    """v0.5.2 hotfix: opencli v1.7.22 returns a JSON ARRAY, not a dict."""
    fake = json.dumps([
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
    ])

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


async def test_xhs_search_back_compat_dict_response(monkeypatch):
    """Defensive: if opencli ever returns the old {"results": [...]} dict, still works."""
    fake = json.dumps({
        "results": [
            {
                "title": "hi",
                "url": "https://xiaohongshu.com/x",
                "author": "u",
                "content": "...",
                "like_count": 1,
                "comment_count": 0,
                "collect_count": 0,
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

    out = await XiaohongshuAdapter().search("hi")
    assert len(out) == 1
    assert out[0].author == "u"


async def test_xhs_search_invokes_opencli_with_format_json(monkeypatch):
    """v0.5.2 hotfix: opencli uses `--format json`, NOT `--json` (which does not exist)."""
    captured_argv: list = []

    async def fake_exec(*args, **kwargs):
        captured_argv.extend(args)

        class P:
            returncode = 0

            async def communicate(self):
                return (b"[]", b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.xiaohongshu.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda n: "/usr/bin/" + n)

    await XiaohongshuAdapter().search("vibe coding", limit=5)

    assert "--json" not in captured_argv, "v0.5.2: opencli does not support --json"
    assert "--format" in captured_argv
    fmt_index = captured_argv.index("--format")
    assert captured_argv[fmt_index + 1] == "json"
    assert "opencli" in captured_argv
    assert "xiaohongshu" in captured_argv
    assert "search" in captured_argv
    assert "vibe coding" in captured_argv


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


async def test_xhs_truncates_content_but_preserves_full_in_raw(monkeypatch):
    """v0.8: long xhs post body gets truncated in content, full kept in raw."""
    long_body = "种" * 1500
    fake = json.dumps([
        {
            "title": "长种草笔记",
            "url": "https://xiaohongshu.com/discovery/item/long",
            "author": "AI小白",
            "content": long_body,
            "published_at": "2026-05-21T08:00:00Z",
            "like_count": 1,
            "comment_count": 0,
            "collect_count": 0,
        }
    ])

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.xiaohongshu.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda n: "/usr/bin/" + n)

    out = await XiaohongshuAdapter().search("q")
    assert len(out) == 1
    assert out[0].content == "种" * 500 + "…"
    assert len(out[0].content) == 501
    assert out[0].raw["content"] == long_body
    assert len(out[0].raw["content"]) == 1500
