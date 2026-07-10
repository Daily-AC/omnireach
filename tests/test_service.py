import pytest

from omnireach.contract import FetchEnvelope, SearchResult
from omnireach.fetcher import fetch
from omnireach.service import search


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
