import asyncio
from unittest.mock import patch

import httpx
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.exa import ExaAdapter


def _mock_transport(status: int, json_body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body or {})
    return httpx.MockTransport(handler)


def test_is_ready_false_without_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    assert asyncio.run(ExaAdapter().is_ready()) is False


def test_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    assert asyncio.run(ExaAdapter().is_ready()) is True


def test_search_returns_results_with_cost_paid(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    payload = {
        "results": [
            {"title": "Result 1", "url": "https://e/1", "publishedDate": "2026-05-22T10:00:00Z",
             "text": "snippet 1", "author": "alice"},
            {"title": "Result 2", "url": "https://e/2", "text": "snippet 2"},
        ]
    }
    a = ExaAdapter()
    real_client = httpx.AsyncClient(transport=_mock_transport(200, payload))
    with patch("omnireach.adapters.exa.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(a.search("q", limit=5))
    assert len(out) == 2
    assert out[0].source == "exa"
    assert out[0].cost == "paid"
    assert out[0].title == "Result 1"


def test_search_raises_on_401(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "bad")
    a = ExaAdapter()
    real_client = httpx.AsyncClient(transport=_mock_transport(401))
    with patch("omnireach.adapters.exa.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        with pytest.raises(AdapterUnavailable):
            asyncio.run(a.search("q"))


def test_search_raises_without_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(ExaAdapter().search("q"))


def test_search_truncates_content_but_preserves_full_in_raw(monkeypatch):
    """v0.8: long Exa text gets truncated in content, full kept in raw['text']."""
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    long_text = "a" * 1024
    payload = {"results": [
        {"title": "Long article", "url": "https://e/long",
         "text": long_text, "author": "n"}
    ]}
    real_client = httpx.AsyncClient(transport=_mock_transport(200, payload))
    with patch("omnireach.adapters.exa.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(ExaAdapter().search("q", limit=5))
    assert len(out) == 1
    assert out[0].content == "a" * 500 + "…"
    assert len(out[0].content) == 501
    assert out[0].raw["text"] == long_text
    assert len(out[0].raw["text"]) == 1024
