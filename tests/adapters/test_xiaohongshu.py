import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.xiaohongshu import XiaohongshuAdapter, _parse_likes


# OpenCLI v1.7.22+ xhs search keys (real E2E observed 2026-05-27, v0.8.1 hotfix):
# rank (int), author (str), author_url (str), likes (str like "102"),
# title (str), url (str), published_at (str like "2026-04-30").
# body / comment_count / collect_count are NOT exposed — content stays "".
_REAL_OPENCLI_ITEM = {
    "rank": 1,
    "author": "AI小白",
    "author_url": "https://www.xiaohongshu.com/user/profile/abc",
    "likes": "4200",
    "title": "Claude 4.7 上手 5 分钟入门",
    "url": "https://xiaohongshu.com/discovery/item/abc",
    "published_at": "2026-05-21",
}


async def test_xhs_search_parses_real_opencli_shape(monkeypatch):
    """v0.8.1 hotfix: adapter maps real OpenCLI search-result keys."""
    fake = json.dumps([_REAL_OPENCLI_ITEM])

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters._opencli.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda n: "/usr/bin/" + n)

    out = await XiaohongshuAdapter().search("claude", limit=3)
    assert len(out) == 1
    assert out[0].source == "xiaohongshu"
    assert out[0].title == "Claude 4.7 上手 5 分钟入门"
    assert out[0].author == "AI小白"
    assert out[0].ts == "2026-05-21"
    # likes is a string in real OpenCLI output → parsed to int by adapter
    assert out[0].engagement.likes == 4200
    # OpenCLI doesn't expose comments/shares in search results
    assert out[0].engagement.comments is None
    assert out[0].engagement.shares is None
    # OpenCLI doesn't return post body either → content stays ""
    assert out[0].content == ""


async def test_xhs_search_back_compat_dict_response(monkeypatch):
    """Defensive: if opencli ever returns the old {"results": [...]} dict shape, still parses."""
    fake = json.dumps({"results": [_REAL_OPENCLI_ITEM]})

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters._opencli.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda n: "/usr/bin/" + n)

    out = await XiaohongshuAdapter().search("hi")
    assert len(out) == 1
    assert out[0].author == "AI小白"


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

    monkeypatch.setattr("omnireach.adapters._opencli.asyncio.create_subprocess_exec", fake_exec)
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


def test_parse_likes_handles_string_int_none_and_garbage():
    """OpenCLI localizes compact counts; helper normalizes them to integers."""
    assert _parse_likes("102") == 102
    assert _parse_likes("0") == 0
    assert _parse_likes(4200) == 4200
    assert _parse_likes("1.2万") == 12000
    assert _parse_likes("2.6万") == 26000
    assert _parse_likes("1.2k") == 1200
    assert _parse_likes(None) is None
    assert _parse_likes("lots") is None
    assert _parse_likes("") is None
