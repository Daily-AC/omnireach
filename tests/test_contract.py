import pytest
from pydantic import ValidationError

from omnireach.contract import SearchEnvelope, SearchResult, SourceError


def test_search_result_minimum_fields():
    r = SearchResult(
        source="hackernews",
        adapter="builtin",
        title="Show HN: omnireach",
        url="https://example.com/1",
        content="snippet",
        ts="2026-05-25T12:00:00Z",
        score=0.5,
    )
    assert r.source == "hackernews"
    assert r.engagement is None
    assert r.raw == {}


def test_search_result_rejects_unknown_source_type():
    with pytest.raises(ValidationError):
        SearchResult.model_validate(
            {"source": 123, "adapter": "builtin", "title": "x", "url": "x"}
        )


def test_search_envelope_roundtrip():
    env = SearchEnvelope(
        query="claude code",
        ts="2026-05-25T12:00:00Z",
        results=[
            SearchResult(
                source="hackernews",
                adapter="builtin",
                title="t",
                url="https://e.x/1",
                content="c",
                ts="2026-05-25T12:00:00Z",
                score=0.9,
            )
        ],
        errors=[SourceError(source="reddit", error="not configured")],
    )
    payload = env.model_dump_json()
    parsed = SearchEnvelope.model_validate_json(payload)
    assert parsed.results[0].title == "t"
    assert parsed.errors[0].source == "reddit"


def test_search_envelope_empty_results_is_valid():
    env = SearchEnvelope(query="q", ts="2026-05-25T12:00:00Z", results=[], errors=[])
    assert env.results == []


def test_content_short_unchanged():
    """Content <= 500 chars is returned as-is (lower boundary case at 499)."""
    short = "x" * 499
    r = SearchResult(
        source="hackernews", adapter="builtin", title="t", url="https://e.x/1",
        content=short,
    )
    assert r.content == short
    assert len(r.content) == 499


def test_content_exact_500_unchanged():
    """Content == 500 chars is on the boundary; not truncated."""
    exact = "x" * 500
    r = SearchResult(
        source="hackernews", adapter="builtin", title="t", url="https://e.x/1",
        content=exact,
    )
    assert r.content == exact
    assert len(r.content) == 500


def test_content_long_gets_truncated_with_ellipsis():
    """Content > 500 chars is truncated to first 500 chars + '…'."""
    long = "y" * 600
    r = SearchResult(
        source="exa", adapter="exa-api", title="t", url="https://e.x/1",
        content=long,
    )
    assert r.content == "y" * 500 + "…"
    assert len(r.content) == 501  # 500 chars + 1 ellipsis char
    assert r.content.endswith("…")


def test_content_empty_unchanged():
    """Empty content stays empty (no spurious ellipsis)."""
    r = SearchResult(
        source="hackernews", adapter="builtin", title="t", url="https://e.x/1",
        content="",
    )
    assert r.content == ""


def test_content_cjk_truncates_by_character_count():
    """CJK content truncates by character count, not byte count."""
    # 1000 汉字, each is 1 Python char but 3 UTF-8 bytes
    cjk = "微" * 1000
    r = SearchResult(
        source="wechat", adapter="exa-api", title="t", url="https://mp.weixin.qq.com/x",
        content=cjk,
    )
    assert r.content == "微" * 500 + "…"
    assert len(r.content) == 501  # by character count
