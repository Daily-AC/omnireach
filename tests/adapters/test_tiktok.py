from unittest.mock import AsyncMock

from omnireach.adapters.tiktok import TikTokAdapter
from omnireach.browser_transport import BrowserCommandResult


_REAL_ITEM = {
    "url": "https://www.tiktok.com/@dev/video/7234",
    "desc": "Quick tour of Claude 4.7 - 60 sec demo of the new editor",
    "author": "dev",
    "plays": 120000,
    "likes": 8400,
    "comments": 312,
    "shares": 540,
    "rank": 1,
}


async def test_tiktok_search_parses_real_shape(monkeypatch):
    run = AsyncMock(
        return_value=BrowserCommandResult(adapter="native-chrome", items=[_REAL_ITEM])
    )
    monkeypatch.setattr("omnireach.adapters.tiktok.run_browser_json", run)

    out = await TikTokAdapter().search("claude", limit=3)

    assert len(out) == 1
    assert out[0].adapter == "native-chrome"
    assert out[0].author == "dev"
    assert out[0].engagement.views == 120000
    assert out[0].engagement.likes == 8400
    assert out[0].engagement.comments == 312
    assert out[0].engagement.shares == 540
    run.assert_awaited_once_with(
        "tiktok",
        "search",
        {"query": "claude", "limit": 3},
        ("tiktok", "search", "--limit", "3", "claude"),
    )


async def test_tiktok_title_truncates_long_desc(monkeypatch):
    item = {**_REAL_ITEM, "desc": "x" * 200}
    monkeypatch.setattr(
        "omnireach.adapters.tiktok.run_browser_json",
        AsyncMock(return_value=BrowserCommandResult(adapter="opencli", items=[item])),
    )

    out = await TikTokAdapter().search("x")

    assert out[0].title.endswith("…")
    assert len(out[0].title) <= 81
    assert out[0].content == "x" * 200


async def test_tiktok_is_ready_accepts_native_bridge_or_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.tiktok.bridge_configured", lambda: True)
    monkeypatch.setattr("omnireach.adapters.tiktok.shutil.which", lambda _: None)
    assert await TikTokAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.tiktok.bridge_configured", lambda: False)
    monkeypatch.setattr("omnireach.adapters.tiktok.shutil.which", lambda _: "/bin/opencli")
    assert await TikTokAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.tiktok.shutil.which", lambda _: None)
    assert await TikTokAdapter().is_ready() is False
