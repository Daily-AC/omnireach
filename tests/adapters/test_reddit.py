import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.reddit import RedditAdapter


async def test_reddit_search_parses_agent_reach_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "How does Claude 4.7 prompt caching actually work?",
                "url": "https://reddit.com/r/ClaudeAI/comments/abc",
                "subreddit": "ClaudeAI",
                "author": "u/alice",
                "selftext": "I've been testing...",
                "score": 245,
                "num_comments": 67,
                "created_utc": "2026-05-20T12:00:00Z",
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.reddit.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(
        "omnireach.adapters.reddit.shutil.which",
        lambda n: "/usr/bin/" + n,  # both binaries exist
    )

    out = await RedditAdapter().search("claude", limit=3)
    assert len(out) == 1
    assert out[0].source == "reddit"
    assert out[0].author == "u/alice"
    assert out[0].engagement.likes == 245
    assert out[0].engagement.comments == 67
    assert "ClaudeAI" in out[0].raw.get("subreddit", "")


async def test_reddit_missing_agent_reach(monkeypatch):
    monkeypatch.setattr(
        "omnireach.adapters.reddit.shutil.which",
        lambda n: None if n == "agent-reach" else "/usr/bin/" + n,
    )
    with pytest.raises(AdapterUnavailable) as exc:
        await RedditAdapter().search("x")
    assert "agent-reach" in str(exc.value)


async def test_reddit_missing_rdt_cli(monkeypatch):
    monkeypatch.setattr(
        "omnireach.adapters.reddit.shutil.which",
        lambda n: None if n == "rdt-cli" else "/usr/bin/" + n,
    )
    with pytest.raises(AdapterUnavailable) as exc:
        await RedditAdapter().search("x")
    assert "rdt-cli" in str(exc.value)


async def test_reddit_is_ready_requires_both_binaries(monkeypatch):
    monkeypatch.setattr(
        "omnireach.adapters.reddit.shutil.which",
        lambda n: "/usr/bin/" + n,
    )
    assert await RedditAdapter().is_ready() is True

    monkeypatch.setattr(
        "omnireach.adapters.reddit.shutil.which",
        lambda n: None if n == "rdt-cli" else "/usr/bin/" + n,
    )
    assert await RedditAdapter().is_ready() is False
