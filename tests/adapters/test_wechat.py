import asyncio
import json
from unittest.mock import patch

import httpx
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.wechat import WeChatAdapter


def _mock_transport(status, body=None):
    def handler(request):
        return httpx.Response(status, json=body or {})
    return httpx.MockTransport(handler)


def test_is_ready_false_without_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    assert asyncio.run(WeChatAdapter().is_ready()) is False


def test_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    assert asyncio.run(WeChatAdapter().is_ready()) is True


def test_search_sends_include_domains(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    captured = {}

    def handler(request):
        captured["body"] = request.read()
        return httpx.Response(200, json={"results": [
            {"title": "公众号 1", "url": "https://mp.weixin.qq.com/s/abc",
             "publishedDate": "2026-05-22T10:00:00Z", "text": "正文"}
        ]})

    real_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("omnireach.adapters.wechat.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(WeChatAdapter().search("q", limit=5))
    body = json.loads(captured["body"])
    assert body["includeDomains"] == ["mp.weixin.qq.com"]
    assert len(out) == 1
    assert out[0].source == "wechat"
    assert out[0].cost == "paid"
    assert "mp.weixin.qq.com" in out[0].url


def test_search_raises_on_401(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "bad")
    real_client = httpx.AsyncClient(transport=_mock_transport(401))
    with patch("omnireach.adapters.wechat.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        with pytest.raises(AdapterUnavailable):
            asyncio.run(WeChatAdapter().search("q"))


def test_search_raises_without_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(WeChatAdapter().search("q"))
