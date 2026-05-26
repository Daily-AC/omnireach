"""Unit tests for the Sogou wechat backend (v0.9). Uses captured fixture."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from omnireach.adapters._wechat_sogou import parse_sogou_serp, search_sogou
from omnireach.adapters.base import AdapterUnavailable

FIXTURE = Path(__file__).parent / "fixtures" / "sogou_wechat_serp.html"


@pytest.fixture
def sogou_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_extracts_results(sogou_html):
    """Real Sogou SERP fixture parses into normalized SearchResults."""
    out = parse_sogou_serp(sogou_html, limit=5)
    assert 1 <= len(out) <= 5
    first = out[0]
    assert first.source == "wechat"
    assert first.adapter == "sogou"
    assert first.cost == "free"
    assert first.title  # non-empty
    assert first.url.startswith("https://weixin.sogou.com/link?url=")
    # snippet may be short, but must be a string
    assert isinstance(first.content, str)


def test_parse_respects_limit(sogou_html):
    out = parse_sogou_serp(sogou_html, limit=2)
    assert len(out) <= 2


def test_parse_extracts_timestamp_when_present(sogou_html):
    """At least one result should have an ISO ts from the timeConvert() script."""
    out = parse_sogou_serp(sogou_html, limit=10)
    iso_count = sum(1 for r in out if r.ts and r.ts.endswith("Z") and "T" in r.ts)
    assert iso_count > 0, f"no timestamps parsed; got {[r.ts for r in out]}"


def test_parse_preserves_raw_html(sogou_html):
    """raw dict carries item-level HTML for downstream inspection."""
    out = parse_sogou_serp(sogou_html, limit=1)
    assert "item_html" in out[0].raw
    assert "<li" in out[0].raw["item_html"]


def test_parse_empty_html_returns_empty():
    """Captcha / blocked / empty SERP returns []."""
    out = parse_sogou_serp("<html><body>no results</body></html>", limit=10)
    assert out == []


def test_search_sogou_raises_on_captcha(monkeypatch):
    """anti-bot challenge surface raises AdapterUnavailable."""
    captcha_body = "<html><body>请输入验证码 antispider</body></html>"

    class FakeResp:
        status_code = 200
        text = captcha_body

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url): return FakeResp()

    monkeypatch.setattr("omnireach.adapters._wechat_sogou.httpx.Client", FakeClient)
    monkeypatch.setattr("omnireach.adapters._wechat_sogou._STEALTHY", None)

    with pytest.raises(AdapterUnavailable) as exc:
        asyncio.run(search_sogou("q"))
    assert "captcha" in str(exc.value).lower() or "anti-bot" in str(exc.value).lower()


def test_search_sogou_raises_on_5xx(monkeypatch):
    class FakeResp:
        status_code = 503
        text = ""

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url): return FakeResp()

    monkeypatch.setattr("omnireach.adapters._wechat_sogou.httpx.Client", FakeClient)
    monkeypatch.setattr("omnireach.adapters._wechat_sogou._STEALTHY", None)

    with pytest.raises(AdapterUnavailable) as exc:
        asyncio.run(search_sogou("q"))
    assert "503" in str(exc.value)
