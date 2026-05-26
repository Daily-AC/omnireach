import asyncio
import os
from unittest.mock import AsyncMock
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.bilibili import BilibiliAdapter
from omnireach.contract import SearchResult


def _fake_api_result(title="bilibili-api hit"):
    return SearchResult(source="bilibili", adapter="bilibili-api", title=title,
                        url="https://www.bilibili.com/video/BVabc",
                        content="snippet", cost="free")


def _fake_exa_result(title="exa hit"):
    return SearchResult(source="bilibili", adapter="exa-api", title=title,
                        url="https://www.bilibili.com/video/BVxyz",
                        content="text", cost="paid")


def test_bilibili_is_ready_always_true(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    assert asyncio.run(BilibiliAdapter().is_ready()) is True


def test_bilibili_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    assert asyncio.run(BilibiliAdapter().is_ready()) is True


def test_bilibili_prefers_exa_when_key_present(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    fake_exa = AsyncMock(return_value=[_fake_exa_result()])
    fake_api = AsyncMock(return_value=[_fake_api_result()])
    monkeypatch.setattr("omnireach.adapters.bilibili._search_exa", fake_exa)
    monkeypatch.setattr("omnireach.adapters.bilibili.search_bilibili", fake_api)
    out = asyncio.run(BilibiliAdapter().search("q"))
    assert len(out) == 1 and out[0].adapter == "exa-api"
    fake_exa.assert_awaited_once()
    fake_api.assert_not_awaited()


def test_bilibili_falls_back_to_api_when_exa_fails(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    fake_exa = AsyncMock(side_effect=AdapterUnavailable("bilibili:exa", "401"))
    fake_api = AsyncMock(return_value=[_fake_api_result()])
    monkeypatch.setattr("omnireach.adapters.bilibili._search_exa", fake_exa)
    monkeypatch.setattr("omnireach.adapters.bilibili.search_bilibili", fake_api)
    out = asyncio.run(BilibiliAdapter().search("q"))
    assert len(out) == 1 and out[0].adapter == "bilibili-api"
    fake_exa.assert_awaited_once()
    fake_api.assert_awaited_once()


def test_bilibili_uses_api_when_no_exa_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    fake_api = AsyncMock(return_value=[_fake_api_result()])
    monkeypatch.setattr("omnireach.adapters.bilibili.search_bilibili", fake_api)
    out = asyncio.run(BilibiliAdapter().search("q"))
    assert len(out) == 1 and out[0].adapter == "bilibili-api"


def test_bilibili_propagates_api_failure_when_no_exa_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    fake_api = AsyncMock(side_effect=AdapterUnavailable("bilibili:api", "503"))
    monkeypatch.setattr("omnireach.adapters.bilibili.search_bilibili", fake_api)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(BilibiliAdapter().search("q"))
