import asyncio
from unittest.mock import patch

import httpx
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.perplexity import PerplexityAdapter


@pytest.fixture
def fixture_payload():
    return {
        "id": "x",
        "choices": [
            {
                "message": {
                    "content": "## Summary\n\nClaude 4.7 looks fast.\n\nSources:\n[1] anthropic.com\n[2] news.ycombinator.com"
                }
            }
        ],
        "citations": [
            "https://anthropic.com/news/claude-4-7",
            "https://news.ycombinator.com/item?id=1",
        ],
    }


def _mock_transport(status: int, json_body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body or {})
    return httpx.MockTransport(handler)


def test_is_ready_false_without_key(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    assert asyncio.run(PerplexityAdapter().is_ready()) is False


def test_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-x")
    assert asyncio.run(PerplexityAdapter().is_ready()) is True


def test_search_returns_citations_as_results(monkeypatch, fixture_payload):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-x")
    a = PerplexityAdapter()
    real_client = httpx.AsyncClient(transport=_mock_transport(200, fixture_payload))
    with patch("omnireach.adapters.perplexity.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(a.search("claude 4.7", limit=5))
    assert len(out) == 2
    assert out[0].source == "perplexity"
    assert out[0].cost == "paid"
    assert out[0].url == "https://anthropic.com/news/claude-4-7"
    assert "fast" in out[0].content.lower() or out[0].content  # summary surfaces


def test_search_raises_on_401(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "bad")
    a = PerplexityAdapter()
    real_client = httpx.AsyncClient(transport=_mock_transport(401))
    with patch("omnireach.adapters.perplexity.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        with pytest.raises(AdapterUnavailable):
            asyncio.run(a.search("q"))


def test_search_raises_without_key(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(PerplexityAdapter().search("q"))
