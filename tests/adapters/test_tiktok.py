import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.tiktok import TikTokAdapter


async def test_tiktok_search_parses_opencli_json_array(monkeypatch):
    """opencli v1.7.22+ returns a JSON ARRAY directly."""
    fake = json.dumps([
        {
            "url": "https://www.tiktok.com/@dev/video/7234",
            "desc": "Quick tour of Claude 4.7 — 60 sec demo of the new editor #ai #claude",
            "author": "dev",
            "created_at": "2026-05-20T03:00:00Z",
            "play_count": 120000,
            "digg_count": 8400,
            "comment_count": 312,
            "share_count": 540,
        }
    ])

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.tiktok.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.tiktok.shutil.which", lambda n: "/usr/bin/" + n)

    out = await TikTokAdapter().search("claude", limit=3)
    assert len(out) == 1
    assert out[0].source == "tiktok"
    assert out[0].author == "dev"
    assert out[0].engagement.views == 120000
    assert out[0].engagement.likes == 8400
    assert out[0].engagement.comments == 312
    assert out[0].engagement.shares == 540
    assert out[0].content.startswith("Quick tour")


async def test_tiktok_search_back_compat_dict_response(monkeypatch):
    """Defensive: if opencli ever returns {"results": [...]} dict, still works."""
    fake = json.dumps({
        "results": [
            {
                "url": "https://www.tiktok.com/@u/video/1",
                "desc": "hi",
                "author": "u",
                "play_count": 10,
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.tiktok.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.tiktok.shutil.which", lambda n: "/usr/bin/" + n)

    out = await TikTokAdapter().search("hi")
    assert len(out) == 1
    assert out[0].author == "u"


async def test_tiktok_search_invokes_opencli_with_format_json(monkeypatch):
    """opencli uses `--format json`, NOT `--json` (which does not exist)."""
    captured_argv: list = []

    async def fake_exec(*args, **kwargs):
        captured_argv.extend(args)

        class P:
            returncode = 0

            async def communicate(self):
                return (b"[]", b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.tiktok.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.tiktok.shutil.which", lambda n: "/usr/bin/" + n)

    await TikTokAdapter().search("vibe coding", limit=5)

    assert "--json" not in captured_argv, "opencli does not support --json"
    assert "--format" in captured_argv
    fmt_index = captured_argv.index("--format")
    assert captured_argv[fmt_index + 1] == "json"
    assert "opencli" in captured_argv
    assert "tiktok" in captured_argv
    assert "search" in captured_argv
    assert "vibe coding" in captured_argv


async def test_tiktok_title_truncates_long_desc(monkeypatch):
    long_desc = "x" * 200
    fake = json.dumps([{"url": "https://www.tiktok.com/@u/video/1", "desc": long_desc, "author": "u"}])

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.tiktok.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.tiktok.shutil.which", lambda n: "/usr/bin/" + n)

    out = await TikTokAdapter().search("x")
    assert out[0].title.endswith("…")
    assert len(out[0].title) <= 82
    assert out[0].content == long_desc


async def test_tiktok_missing_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.tiktok.shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable) as exc:
        await TikTokAdapter().search("x")
    assert "opencli" in str(exc.value).lower()


async def test_tiktok_is_ready_requires_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.tiktok.shutil.which", lambda n: "/usr/bin/opencli")
    assert await TikTokAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.tiktok.shutil.which", lambda n: None)
    assert await TikTokAdapter().is_ready() is False
