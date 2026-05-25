import asyncio
import json
from unittest.mock import patch

import httpx
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.bilibili import BilibiliAdapter


def _mock_transport(status, body=None):
    def handler(request):
        return httpx.Response(status, json=body or {})
    return httpx.MockTransport(handler)


def test_is_ready_false_without_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    assert asyncio.run(BilibiliAdapter().is_ready()) is False


def test_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    assert asyncio.run(BilibiliAdapter().is_ready()) is True


def test_search_sends_include_domains(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    captured = {}

    def handler(request):
        captured["body"] = request.read()
        return httpx.Response(200, json={"results": [
            {"title": "B站 视频 1", "url": "https://www.bilibili.com/video/BVabc",
             "publishedDate": "2026-05-22T10:00:00Z", "text": "简介"}
        ]})

    real_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("omnireach.adapters.bilibili.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(BilibiliAdapter().search("q", limit=5))
    body = json.loads(captured["body"])
    assert set(body["includeDomains"]) == {"bilibili.com", "www.bilibili.com"}
    assert len(out) == 1
    assert out[0].source == "bilibili"
    assert out[0].cost == "paid"
    assert "bilibili.com" in out[0].url


def test_search_raises_on_401(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "bad")
    real_client = httpx.AsyncClient(transport=_mock_transport(401))
    with patch("omnireach.adapters.bilibili.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        with pytest.raises(AdapterUnavailable):
            asyncio.run(BilibiliAdapter().search("q"))


def test_search_raises_without_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(BilibiliAdapter().search("q"))
