from unittest.mock import AsyncMock

from omnireach.adapters.twitter import TwitterAdapter
from omnireach.browser_transport import BrowserCommandResult


async def test_twitter_search_parses_real_shape(monkeypatch):
    run = AsyncMock(
        return_value=BrowserCommandResult(
            adapter="native-chrome",
            items=[
                {
                    "text": "Claude 4.7 prompt caching is wild",
                    "url": "https://x.com/alice/status/123",
                    "author": "alice",
                    "created_at": "2026-05-20T10:00:00Z",
                    "likes": 1234,
                    "retweets": 42,
                    "replies": 7,
                    "views": "56789",
                }
            ],
        )
    )
    monkeypatch.setattr("omnireach.adapters.twitter.run_browser_json", run)

    out = await TwitterAdapter().search("claude", limit=3)

    assert len(out) == 1
    assert out[0].adapter == "native-chrome"
    assert out[0].author == "alice"
    assert out[0].engagement.likes == 1234
    assert out[0].engagement.shares == 42
    assert out[0].engagement.comments == 7
    assert out[0].engagement.views == 56789
    run.assert_awaited_once_with(
        "twitter",
        "search",
        {"query": "claude", "limit": 3},
        ("twitter", "search", "--limit", "3", "claude"),
    )


async def test_twitter_is_ready_accepts_native_bridge_or_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.twitter.bridge_configured", lambda: True)
    monkeypatch.setattr("omnireach.adapters.twitter.shutil.which", lambda _: None)
    assert await TwitterAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.twitter.bridge_configured", lambda: False)
    monkeypatch.setattr("omnireach.adapters.twitter.shutil.which", lambda _: "/bin/opencli")
    assert await TwitterAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.twitter.shutil.which", lambda _: None)
    assert await TwitterAdapter().is_ready() is False
