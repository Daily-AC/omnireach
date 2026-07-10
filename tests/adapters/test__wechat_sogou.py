"""Unit tests for the Sogou wechat backend (v0.9). Uses captured fixture."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from omnireach.adapters._wechat_sogou import (
    _extract_wechat_url,
    parse_sogou_serp,
    search_sogou,
)
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


def test_extract_wechat_url_reassembles_sogou_javascript_fragments():
    body = """
    <script>
      var url = '';
      url += 'https://mp.';
      url += 'weixin.qq.c';
      url += 'om/s?src=11';
      url += '&timestamp=123';
      window.location.replace(url)
    </script>
    """
    assert _extract_wechat_url(body) == (
        "https://mp.weixin.qq.com/s?src=11&timestamp=123"
    )


def test_search_sogou_resolves_direct_wechat_url_in_same_http_session(
    monkeypatch, sogou_html
):
    direct_page = """
    <script>
      var url = '';
      url += 'https://mp.weixin.qq.com/s/';
      url += 'real-article-id';
      window.location.replace(url)
    </script>
    """

    class FakeResp:
        def __init__(self, text, url):
            self.status_code = 200
            self.text = text
            self.url = url

    class FakeClient:
        def __init__(self, *a, **k):
            self.calls = 0

        def __enter__(self): return self
        def __exit__(self, *a): pass

        def get(self, url, headers=None):
            self.calls += 1
            if self.calls == 1:
                return FakeResp(sogou_html, url)
            return FakeResp(direct_page, url)

    monkeypatch.setattr("omnireach.adapters._wechat_sogou.httpx.Client", FakeClient)

    out = asyncio.run(search_sogou("q", limit=1))

    assert out[0].url == "https://mp.weixin.qq.com/s/real-article-id"
    assert out[0].raw["sogou_url"].startswith("https://weixin.sogou.com/link?")


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
    with pytest.raises(AdapterUnavailable) as exc:
        asyncio.run(search_sogou("q"))
    assert "503" in str(exc.value)
