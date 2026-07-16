from unittest.mock import AsyncMock

from omnireach.adapters.xiaohongshu import XiaohongshuAdapter, _parse_likes
from omnireach.browser_transport import BrowserCommandResult


_REAL_ITEM = {
    "rank": 1,
    "author": "AI小白",
    "author_url": "https://www.xiaohongshu.com/user/profile/abc",
    "likes": "4200",
    "title": "Claude 4.7 上手 5 分钟入门",
    "url": "https://www.xiaohongshu.com/explore/697f6c740000000000000000",
    "published_at": "2026-05-21",
}


async def test_xhs_search_parses_real_shape(monkeypatch):
    run = AsyncMock(
        return_value=BrowserCommandResult(adapter="native-chrome", items=[_REAL_ITEM])
    )
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.run_browser_json", run)

    out = await XiaohongshuAdapter().search("claude", limit=3)

    assert len(out) == 1
    assert out[0].adapter == "native-chrome"
    assert out[0].title == "Claude 4.7 上手 5 分钟入门"
    assert out[0].author == "AI小白"
    assert out[0].ts == "2026-05-21"
    assert out[0].engagement.likes == 4200
    assert out[0].content == ""
    run.assert_awaited_once_with(
        "xiaohongshu",
        "search",
        {"query": "claude", "limit": 3},
        ("xiaohongshu", "search", "--limit", "3", "claude"),
    )


async def test_xhs_is_ready_accepts_native_bridge_or_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.bridge_configured", lambda: True)
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda _: None)
    assert await XiaohongshuAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.xiaohongshu.bridge_configured", lambda: False)
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda _: "/bin/opencli")
    assert await XiaohongshuAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda _: None)
    assert await XiaohongshuAdapter().is_ready() is False


def test_parse_likes_handles_string_int_none_and_garbage():
    assert _parse_likes("102") == 102
    assert _parse_likes(4200) == 4200
    assert _parse_likes("1.2万") == 12000
    assert _parse_likes("1.2k") == 1200
    assert _parse_likes(None) is None
    assert _parse_likes("lots") is None
