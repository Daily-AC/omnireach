import asyncio
import os
from unittest.mock import AsyncMock
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.wechat import WeChatAdapter
from omnireach.contract import SearchResult


def _fake_sogou_result(title="sogou hit"):
    return SearchResult(source="wechat", adapter="sogou", title=title,
                        url="https://weixin.sogou.com/link?url=abc",
                        content="snippet", cost="free")


def _fake_exa_result(title="exa hit"):
    return SearchResult(source="wechat", adapter="exa-api", title=title,
                        url="https://mp.weixin.qq.com/s/xyz",
                        content="text", cost="paid")


def test_wechat_is_ready_always_true(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    assert asyncio.run(WeChatAdapter().is_ready()) is True


def test_wechat_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    assert asyncio.run(WeChatAdapter().is_ready()) is True


def test_wechat_prefers_exa_when_key_present(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    fake_exa = AsyncMock(return_value=[_fake_exa_result()])
    fake_sogou = AsyncMock(return_value=[_fake_sogou_result()])
    monkeypatch.setattr("omnireach.adapters.wechat._search_exa", fake_exa)
    monkeypatch.setattr("omnireach.adapters.wechat.search_sogou", fake_sogou)
    out = asyncio.run(WeChatAdapter().search("q"))
    assert len(out) == 1 and out[0].adapter == "exa-api"
    fake_exa.assert_awaited_once()
    fake_sogou.assert_not_awaited()


def test_wechat_falls_back_to_sogou_when_exa_fails(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    fake_exa = AsyncMock(side_effect=AdapterUnavailable("wechat:exa", "401"))
    fake_sogou = AsyncMock(return_value=[_fake_sogou_result()])
    monkeypatch.setattr("omnireach.adapters.wechat._search_exa", fake_exa)
    monkeypatch.setattr("omnireach.adapters.wechat.search_sogou", fake_sogou)
    out = asyncio.run(WeChatAdapter().search("q"))
    assert len(out) == 1 and out[0].adapter == "sogou"
    fake_exa.assert_awaited_once()
    fake_sogou.assert_awaited_once()


def test_wechat_uses_sogou_when_no_exa_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    fake_sogou = AsyncMock(return_value=[_fake_sogou_result()])
    monkeypatch.setattr("omnireach.adapters.wechat.search_sogou", fake_sogou)
    out = asyncio.run(WeChatAdapter().search("q"))
    assert len(out) == 1 and out[0].adapter == "sogou"


def test_wechat_propagates_sogou_failure_when_no_exa_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    fake_sogou = AsyncMock(side_effect=AdapterUnavailable("wechat:sogou", "503"))
    monkeypatch.setattr("omnireach.adapters.wechat.search_sogou", fake_sogou)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(WeChatAdapter().search("q"))
