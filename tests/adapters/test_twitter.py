import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.twitter import TwitterAdapter


async def test_twitter_search_parses_opencli_json_array(monkeypatch):
    """v0.5.2 hotfix: opencli v1.7.22 returns a JSON ARRAY, not a dict."""
    fake = json.dumps([
        {
            "text": "Claude 4.7 prompt caching is wild",
            "url": "https://twitter.com/alice/status/123",
            "author": "alice",
            "created_at": "2026-05-20T10:00:00Z",
            "like_count": 1234,
            "retweet_count": 56,
            "reply_count": 12,
        }
    ])

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.twitter.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.twitter.shutil.which", lambda n: "/usr/bin/" + n)

    out = await TwitterAdapter().search("claude", limit=3)
    assert len(out) == 1
    assert out[0].source == "twitter"
    assert out[0].author == "alice"
    assert out[0].engagement.likes == 1234
    assert out[0].engagement.shares == 56
    assert out[0].engagement.comments == 12
    assert "Claude 4.7" in out[0].title


async def test_twitter_search_back_compat_dict_response(monkeypatch):
    """Defensive: if opencli ever returns the old {"results": [...]} dict, still works."""
    fake = json.dumps({
        "results": [
            {
                "text": "hello world",
                "url": "https://twitter.com/x/status/1",
                "author": "x",
                "like_count": 1,
                "retweet_count": 0,
                "reply_count": 0,
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.twitter.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.twitter.shutil.which", lambda n: "/usr/bin/" + n)

    out = await TwitterAdapter().search("hello")
    assert len(out) == 1
    assert out[0].author == "x"


async def test_twitter_search_invokes_opencli_with_format_json(monkeypatch):
    """v0.5.2 hotfix: opencli uses `--format json`, NOT `--json` (which does not exist)."""
    captured_argv: list = []

    async def fake_exec(*args, **kwargs):
        captured_argv.extend(args)

        class P:
            returncode = 0

            async def communicate(self):
                return (b"[]", b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.twitter.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.twitter.shutil.which", lambda n: "/usr/bin/" + n)

    await TwitterAdapter().search("vibe coding", limit=5)

    assert "--json" not in captured_argv, "v0.5.2: opencli does not support --json"
    assert "--format" in captured_argv
    fmt_index = captured_argv.index("--format")
    assert captured_argv[fmt_index + 1] == "json"
    assert "opencli" in captured_argv
    assert "twitter" in captured_argv
    assert "search" in captured_argv
    assert "vibe coding" in captured_argv


async def test_twitter_missing_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.twitter.shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable) as exc:
        await TwitterAdapter().search("x")
    assert "opencli" in str(exc.value).lower()


async def test_twitter_is_ready_requires_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.twitter.shutil.which", lambda n: "/usr/bin/opencli")
    assert await TwitterAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.twitter.shutil.which", lambda n: None)
    assert await TwitterAdapter().is_ready() is False
