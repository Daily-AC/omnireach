import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.google import GoogleAdapter


async def test_google_search_normalizes_real_opencli_shape(monkeypatch):
    async def fake_run(source, *args):
        assert source == "google"
        return [
            {
                "snippet": "Frontier intelligence for professional work.",
                "title": "GPT-5.6: Frontier intelligence",
                "type": "result",
                "url": "https://openai.com/index/gpt-5-6/",
            }
        ]

    monkeypatch.setattr("omnireach.adapters.google.run_opencli_json", fake_run)
    monkeypatch.setattr(
        "omnireach.adapters.google.shutil.which", lambda _: "/bin/opencli"
    )

    results = await GoogleAdapter().search("gpt5.6", limit=5)

    assert len(results) == 1
    assert results[0].source == "google"
    assert results[0].adapter == "opencli"
    assert results[0].title == "GPT-5.6: Frontier intelligence"
    assert results[0].url == "https://openai.com/index/gpt-5-6/"
    assert results[0].content == "Frontier intelligence for professional work."
    assert results[0].raw["type"] == "result"


async def test_google_search_skips_rows_without_external_http_url(monkeypatch):
    async def fake_run(source, *args):
        return [
            {
                "type": "paa",
                "title": "What is GPT-5.6?",
                "url": "",
                "snippet": "",
            },
            {
                "type": "result",
                "title": "Internal",
                "url": "javascript:void(0)",
                "snippet": "",
            },
            {
                "type": "snippet",
                "title": "Answer",
                "url": "https://example.com/a",
                "snippet": "",
            },
        ]

    monkeypatch.setattr("omnireach.adapters.google.run_opencli_json", fake_run)
    monkeypatch.setattr(
        "omnireach.adapters.google.shutil.which", lambda _: "/bin/opencli"
    )

    results = await GoogleAdapter().search("gpt5.6")

    assert [result.url for result in results] == ["https://example.com/a"]


async def test_google_search_invokes_silent_opencli_bridge(monkeypatch):
    captured = []

    async def fake_run(source, *args):
        captured.extend((source, *args))
        return []

    monkeypatch.setattr("omnireach.adapters.google.run_opencli_json", fake_run)
    monkeypatch.setattr(
        "omnireach.adapters.google.shutil.which", lambda _: "/bin/opencli"
    )

    await GoogleAdapter().search("vibe coding", limit=7)

    assert captured == [
        "google",
        "google",
        "search",
        "vibe coding",
        "--limit",
        "7",
    ]


async def test_google_missing_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.google.shutil.which", lambda _: None)
    with pytest.raises(AdapterUnavailable, match="opencli"):
        await GoogleAdapter().search("gpt5.6")


async def test_google_is_ready_requires_opencli(monkeypatch):
    monkeypatch.setattr(
        "omnireach.adapters.google.shutil.which", lambda _: "/bin/opencli"
    )
    assert await GoogleAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.google.shutil.which", lambda _: None)
    assert await GoogleAdapter().is_ready() is False
