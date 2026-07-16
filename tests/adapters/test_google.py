from unittest.mock import AsyncMock

from omnireach.adapters.google import GoogleAdapter
from omnireach.browser_transport import BrowserCommandResult


async def test_google_search_normalizes_real_opencli_shape(monkeypatch):
    run = AsyncMock(
        return_value=BrowserCommandResult(
            adapter="native-chrome",
            items=[
                {
                    "snippet": "Frontier intelligence for professional work.",
                    "title": "GPT-5.6: Frontier intelligence",
                    "type": "result",
                    "url": "https://openai.com/index/gpt-5-6/",
                }
            ],
        )
    )
    monkeypatch.setattr("omnireach.adapters.google.run_browser_json", run)

    results = await GoogleAdapter().search("gpt5.6", limit=5)

    assert len(results) == 1
    assert results[0].source == "google"
    assert results[0].adapter == "native-chrome"
    assert results[0].title == "GPT-5.6: Frontier intelligence"
    assert results[0].url == "https://openai.com/index/gpt-5-6/"
    assert results[0].content == "Frontier intelligence for professional work."
    run.assert_awaited_once_with(
        "google",
        "search",
        {"query": "gpt5.6", "limit": 5},
        ("google", "search", "gpt5.6", "--limit", "5"),
    )


async def test_google_search_skips_rows_without_external_http_url(monkeypatch):
    monkeypatch.setattr(
        "omnireach.adapters.google.run_browser_json",
        AsyncMock(
            return_value=BrowserCommandResult(
                adapter="opencli",
                items=[
                    {"title": "Question", "url": "", "snippet": ""},
                    {"title": "Internal", "url": "javascript:void(0)", "snippet": ""},
                    {"title": "Answer", "url": "https://example.com/a", "snippet": ""},
                ],
            )
        ),
    )

    results = await GoogleAdapter().search("gpt5.6")

    assert [result.url for result in results] == ["https://example.com/a"]


async def test_google_is_ready_accepts_native_bridge_or_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.google.bridge_configured", lambda: True)
    monkeypatch.setattr("omnireach.adapters.google.shutil.which", lambda _: None)
    assert await GoogleAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.google.bridge_configured", lambda: False)
    monkeypatch.setattr("omnireach.adapters.google.shutil.which", lambda _: "/bin/opencli")
    assert await GoogleAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.google.shutil.which", lambda _: None)
    assert await GoogleAdapter().is_ready() is False
