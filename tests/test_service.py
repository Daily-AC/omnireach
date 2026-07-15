import pytest

from omnireach.contract import FetchEnvelope, SearchResult
from omnireach.fetcher import fetch
from omnireach.registry import load_registry
from omnireach.service import augment_with_active_browser_sources, search


def test_fetch_service_returns_typed_success(monkeypatch):
    monkeypatch.setattr(
        "omnireach.fetcher._fetch_via_http",
        lambda url, timeout: "# service body",
    )

    result = fetch("https://example.com", backend="auto", timeout=5)

    assert isinstance(result, FetchEnvelope)
    assert result.backend == "http"
    assert result.content_markdown == "# service body"
    assert result.errors == []


def test_fetch_service_preserves_attempt_errors(monkeypatch):
    def blocked(url, timeout):
        raise RuntimeError("blocked")

    monkeypatch.setattr("omnireach.fetcher._fetch_via_http", blocked)
    monkeypatch.setattr(
        "omnireach.fetcher._fetch_via_jina",
        lambda url, timeout: "# fallback",
    )

    result = fetch("https://example.com")

    assert result.backend == "jina"
    assert result.content_markdown == "# fallback"
    assert result.errors == ["http: blocked"]


@pytest.mark.asyncio
async def test_search_service_returns_ranked_envelope(monkeypatch):
    async def fake_search(self, query, *, limit=10):
        return [
            SearchResult(
                source="hackernews",
                adapter="builtin",
                title="service result",
                url="https://example.com/result",
                score=0.5,
            )
        ]

    monkeypatch.setattr(
        "omnireach.adapters.hackernews.HackerNewsAdapter.search",
        fake_search,
    )

    envelope = await search(
        "claude", sources=["hackernews"], limit=1, timeout=5
    )

    assert envelope.query == "claude"
    assert [result.source for result in envelope.results] == ["hackernews"]
    assert envelope.errors == []


@pytest.mark.asyncio
async def test_search_service_rejects_unknown_explicit_source():
    with pytest.raises(ValueError, match="unknown source"):
        await search("claude", sources=["not-a-source"])


def test_auto_search_adds_google_and_twitter_when_opencli_exists(monkeypatch):
    monkeypatch.setattr("omnireach.service.shutil.which", lambda _: "/bin/opencli")

    result = augment_with_active_browser_sources(
        ["hackernews"], load_registry(), explicit_sources=None, mode="auto"
    )

    assert result == ["hackernews", "google", "twitter"]


def test_deep_search_adds_google_and_twitter_when_opencli_exists(monkeypatch):
    monkeypatch.setattr("omnireach.service.shutil.which", lambda _: "/bin/opencli")

    result = augment_with_active_browser_sources(
        ["hackernews"], load_registry(), explicit_sources=None, mode="deep"
    )

    assert result == ["hackernews", "google", "twitter"]


def test_quick_search_never_adds_browser_sources(monkeypatch):
    monkeypatch.setattr("omnireach.service.shutil.which", lambda _: "/bin/opencli")

    result = augment_with_active_browser_sources(
        ["hackernews"], load_registry(), explicit_sources=None, mode="quick"
    )

    assert result == ["hackernews"]


def test_explicit_sources_are_exact(monkeypatch):
    monkeypatch.setattr("omnireach.service.shutil.which", lambda _: "/bin/opencli")

    result = augment_with_active_browser_sources(
        ["hackernews"],
        load_registry(),
        explicit_sources=["hackernews"],
        mode="auto",
    )

    assert result == ["hackernews"]


def test_auto_search_skips_browser_sources_without_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.service.shutil.which", lambda _: None)

    result = augment_with_active_browser_sources(
        ["hackernews"], load_registry(), explicit_sources=None, mode="auto"
    )

    assert result == ["hackernews"]


def test_auto_search_does_not_duplicate_browser_sources(monkeypatch):
    monkeypatch.setattr("omnireach.service.shutil.which", lambda _: "/bin/opencli")

    result = augment_with_active_browser_sources(
        ["google", "twitter"], load_registry(), explicit_sources=None, mode="deep"
    )

    assert result == ["google", "twitter"]


@pytest.mark.asyncio
async def test_search_service_dispatches_auto_browser_sources(monkeypatch):
    captured: list[str] = []

    async def fake_run(self, adapters, query):
        captured.extend(adapters)
        return [], []

    monkeypatch.setattr("omnireach.service.shutil.which", lambda _: "/bin/opencli")
    monkeypatch.setattr("omnireach.service.Dispatcher.run", fake_run)
    for env_name in (
        "TAVILY_API_KEY",
        "BRAVE_API_KEY",
        "PERPLEXITY_API_KEY",
        "EXA_API_KEY",
    ):
        monkeypatch.delenv(env_name, raising=False)

    await search("gpt5.6", mode="auto")

    assert "google" in captured
    assert "twitter" in captured


@pytest.mark.asyncio
async def test_explicit_timeout_overrides_per_source_defaults(monkeypatch):
    captured = {}

    class FakeDispatcher:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def run(self, adapters, query):
            return [], []

    monkeypatch.setattr("omnireach.service.Dispatcher", FakeDispatcher)

    await search("python", sources=["hackernews"], timeout=17)

    assert captured["timeout"] == 17
    assert captured["timeouts_by_source"] == {}


@pytest.mark.asyncio
async def test_omitted_timeout_uses_registry_defaults(monkeypatch):
    captured = {}

    class FakeDispatcher:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def run(self, adapters, query):
            return [], []

    monkeypatch.setattr("omnireach.service.Dispatcher", FakeDispatcher)

    await search("python", sources=["reddit"])

    assert captured["timeouts_by_source"]["reddit"] == 60.0
