from unittest.mock import AsyncMock

from omnireach.adapters.douyin import DouyinAdapter
from omnireach.browser_transport import BrowserCommandResult


async def test_douyin_search_normalizes_real_result_shape(monkeypatch):
    """Shape captured from a real Douyin search result on 2026-05-26."""
    run = AsyncMock(
        return_value=BrowserCommandResult(
            adapter="native-chrome",
            items=[
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
            ],
        )
    )
    monkeypatch.setattr("omnireach.adapters.douyin.run_browser_json", run)

    out = await DouyinAdapter().search("claude code", limit=3)

    assert len(out) == 1
    assert out[0].source == "douyin"
    assert out[0].adapter == "native-chrome"
    assert out[0].author == "秋芝2046"
    assert out[0].engagement.likes == 40000
    assert out[0].engagement.views is None
    assert out[0].engagement.comments is None
    assert out[0].engagement.shares is None
    assert out[0].ts is None
    run.assert_awaited_once_with(
        "douyin",
        "search",
        {"query": "claude code", "limit": 3},
        ("douyin", "search", "--limit", "3", "claude code"),
    )


async def test_douyin_search_preserves_opencli_attribution(monkeypatch):
    monkeypatch.setattr(
        "omnireach.adapters.douyin.run_browser_json",
        AsyncMock(
            return_value=BrowserCommandResult(
                adapter="opencli",
                items=[
                    {
                        "desc": "fallback",
                        "url": "https://www.douyin.com/video/1",
                    }
                ],
            )
        ),
    )

    out = await DouyinAdapter().search("x")

    assert out[0].adapter == "opencli"


async def test_douyin_search_zero_likes_normalized_to_none(monkeypatch):
    monkeypatch.setattr(
        "omnireach.adapters.douyin.run_browser_json",
        AsyncMock(
            return_value=BrowserCommandResult(
                adapter="native-chrome",
                items=[
                    {
                        "desc": "x",
                        "author": "u",
                        "url": "https://www.douyin.com/video/1",
                        "likes": 0,
                    }
                ],
            )
        ),
    )

    out = await DouyinAdapter().search("x")

    assert out[0].engagement.likes is None


async def test_douyin_is_ready_accepts_native_bridge_or_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.douyin.bridge_configured", lambda: True)
    monkeypatch.setattr("omnireach.adapters.douyin.shutil.which", lambda name: None)
    assert await DouyinAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.douyin.bridge_configured", lambda: False)
    monkeypatch.setattr(
        "omnireach.adapters.douyin.shutil.which", lambda name: "/usr/bin/opencli"
    )
    assert await DouyinAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.douyin.shutil.which", lambda name: None)
    assert await DouyinAdapter().is_ready() is False
