import asyncio
from unittest.mock import patch

import httpx
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.brave import BraveAdapter


@pytest.fixture
def fixture_payload():
    return {
        "web": {
            "results": [
                {
                    "title": "Brave 1",
                    "url": "https://example.com/1",
                    "description": "desc 1",
                    "age": "2026-05-22T10:00:00",
                },
                {
                    "title": "Brave 2",
                    "url": "https://example.com/2",
                    "description": "desc 2",
                },
            ]
        }
    }


def _mock_transport(status: int, json_body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body or {})
    return httpx.MockTransport(handler)


def test_is_ready_false_without_key(monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    assert asyncio.run(BraveAdapter().is_ready()) is False


def test_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "BSA-x")
    assert asyncio.run(BraveAdapter().is_ready()) is True


def test_search_returns_results(monkeypatch, fixture_payload):
    monkeypatch.setenv("BRAVE_API_KEY", "BSA-x")
    a = BraveAdapter()
    real_client = httpx.AsyncClient(transport=_mock_transport(200, fixture_payload))
    with patch("omnireach.adapters.brave.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(a.search("q", limit=5))
    assert len(out) == 2
    assert out[0].source == "brave"
    assert out[0].cost == "paid"
    assert out[0].title == "Brave 1"


def test_search_raises_on_401(monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "bad")
    a = BraveAdapter()
    real_client = httpx.AsyncClient(transport=_mock_transport(401))
    with patch("omnireach.adapters.brave.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        with pytest.raises(AdapterUnavailable):
            asyncio.run(a.search("q"))


def test_search_raises_without_key(monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(BraveAdapter().search("q"))
