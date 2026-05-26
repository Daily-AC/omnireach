"""Unit tests for B站 API backend (v0.9). Uses captured fixture."""

import asyncio
import json
from pathlib import Path

import pytest

from omnireach.adapters._bilibili_api import (
    parse_bilibili_response,
    search_bilibili,
    _strip_em,
    _ts_iso,
)
from omnireach.adapters.base import AdapterUnavailable

FIXTURE = Path(__file__).parent / "fixtures" / "bilibili_search_response.json"


@pytest.fixture
def bili_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_extracts_video_hits(bili_payload):
    out = parse_bilibili_response(bili_payload, limit=5)
    assert 1 <= len(out) <= 5
    first = out[0]
    assert first.source == "bilibili"
    assert first.adapter == "bilibili-api"
    assert first.cost == "free"
    assert first.title  # non-empty
    assert "<em" not in first.title  # _strip_em removed highlighting
    assert first.url.startswith("https://www.bilibili.com/video/BV")


def test_parse_respects_limit(bili_payload):
    out = parse_bilibili_response(bili_payload, limit=3)
    assert len(out) <= 3


def test_parse_engagement_populated(bili_payload):
    """At least one result should have play/like/review counts as ints."""
    out = parse_bilibili_response(bili_payload, limit=10)
    have_eng = [r for r in out if r.engagement and r.engagement.views is not None]
    assert have_eng, "no engagement.views populated"
    assert isinstance(have_eng[0].engagement.views, int)


def test_parse_ts_iso(bili_payload):
    out = parse_bilibili_response(bili_payload, limit=3)
    iso_count = sum(1 for r in out if r.ts and r.ts.endswith("Z") and "T" in r.ts)
    assert iso_count > 0, f"no timestamps parsed; got {[r.ts for r in out]}"


def test_parse_error_code_returns_empty():
    """B站 returns code != 0 on errors — yield no results, don't crash."""
    payload = {"code": -412, "message": "risk control", "data": None}
    assert parse_bilibili_response(payload, limit=10) == []


def test_parse_missing_video_block_returns_empty():
    """If no result_type='video' block, return []."""
    payload = {"code": 0, "data": {"result": [{"result_type": "live", "data": []}]}}
    assert parse_bilibili_response(payload, limit=10) == []


def test_strip_em_removes_highlight_tags():
    assert _strip_em('<em class="keyword">Claude</em> 4.7 review') == "Claude 4.7 review"
    assert _strip_em("plain text") == "plain text"
    assert _strip_em("") == ""


def test_ts_iso_handles_zero_and_none():
    assert _ts_iso(0) is None
    assert _ts_iso(None) is None
    assert _ts_iso("not-a-number") is None
    assert _ts_iso(1700000000) == "2023-11-14T22:13:20Z"


def test_search_bilibili_raises_on_412(monkeypatch):
    class FakeResp:
        status_code = 412
        def json(self): return {}
    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url, params=None): return FakeResp()
    monkeypatch.setattr("omnireach.adapters._bilibili_api.httpx.Client", FakeClient)
    with pytest.raises(AdapterUnavailable) as exc:
        asyncio.run(search_bilibili("q"))
    assert "412" in str(exc.value)


def test_search_bilibili_raises_on_upstream_error_code(monkeypatch):
    class FakeResp:
        status_code = 200
        def json(self): return {"code": -101, "message": "not logged in"}
    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url, params=None): return FakeResp()
    monkeypatch.setattr("omnireach.adapters._bilibili_api.httpx.Client", FakeClient)
    with pytest.raises(AdapterUnavailable) as exc:
        asyncio.run(search_bilibili("q"))
    assert "-101" in str(exc.value)
