import asyncio
from unittest.mock import patch

import httpx
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.tavily import TavilyAdapter


@pytest.fixture
def fixture_payload():
    return {
        "results": [
            {
                "title": "Claude 4.7 review",
                "url": "https://example.com/a",
                "content": "snippet",
                "published_date": "2026-05-20T10:00:00Z",
            },
            {
                "title": "Anthropic release notes",
                "url": "https://example.com/b",
                "content": "another",
                "published_date": "2026-05-22T08:30:00Z",
            },
        ]
    }


def _mock_transport(status: int, json_body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body or {})
    return httpx.MockTransport(handler)


def test_is_ready_false_without_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    a = TavilyAdapter()
    assert asyncio.run(a.is_ready()) is False


def test_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")
    a = TavilyAdapter()
    assert asyncio.run(a.is_ready()) is True


def test_search_returns_results_with_cost_paid(monkeypatch, fixture_payload):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")
    a = TavilyAdapter()
    real_client = httpx.AsyncClient(transport=_mock_transport(200, fixture_payload))
    with patch("omnireach.adapters.tavily.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(a.search("claude 4.7", limit=5))
    assert len(out) == 2
    assert out[0].source == "tavily"
    assert out[0].cost == "paid"
    assert out[0].title == "Claude 4.7 review"


def test_search_raises_on_401(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "bad")
    a = TavilyAdapter()
    real_client = httpx.AsyncClient(transport=_mock_transport(401))
    with patch("omnireach.adapters.tavily.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        with pytest.raises(AdapterUnavailable):
            asyncio.run(a.search("q"))


def test_search_raises_without_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    a = TavilyAdapter()
    with pytest.raises(AdapterUnavailable):
        asyncio.run(a.search("q"))
