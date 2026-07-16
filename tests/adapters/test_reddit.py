from unittest.mock import AsyncMock

from omnireach.adapters.reddit import RedditAdapter
from omnireach.browser_transport import BrowserCommandResult


_REAL_ITEM = {
    "id": "1u6g6tn",
    "title": "I think Claude Code saved my life.",
    "subreddit": "r/ClaudeCode",
    "author": "TheComplicatedMan",
    "score": 561,
    "comments": 169,
    "url": "https://www.reddit.com/r/ClaudeCode/comments/1u6g6tn/post/",
    "created_utc": 1781529030,
    "selftext": "I was at the prompt working, but did not feel well.",
}


async def test_search_parses_real_shape_and_preserves_transport(monkeypatch):
    run = AsyncMock(
        return_value=BrowserCommandResult(adapter="native-chrome", items=[_REAL_ITEM])
    )
    monkeypatch.setattr("omnireach.adapters.reddit.run_browser_json", run)

    out = await RedditAdapter().search("Claude Code", limit=5)

    assert len(out) == 1
    assert out[0].adapter == "native-chrome"
    assert out[0].author == "TheComplicatedMan"
    assert out[0].engagement.likes == 561
    assert out[0].engagement.comments == 169
    assert out[0].ts == "2026-06-15T13:10:30+00:00"
    run.assert_awaited_once_with(
        "reddit",
        "search",
        {"query": "Claude Code", "limit": 5},
        ("reddit", "search", "Claude Code", "--limit", "5"),
    )


async def test_is_ready_accepts_native_bridge_or_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.reddit.bridge_configured", lambda: True)
    monkeypatch.setattr("omnireach.adapters.reddit.shutil.which", lambda _: None)
    assert await RedditAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.reddit.bridge_configured", lambda: False)
    monkeypatch.setattr("omnireach.adapters.reddit.shutil.which", lambda _: "/bin/opencli")
    assert await RedditAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.reddit.shutil.which", lambda _: None)
    assert await RedditAdapter().is_ready() is False
