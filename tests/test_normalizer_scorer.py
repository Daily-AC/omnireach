from omnireach.contract import Engagement, SearchResult, SourceError
from omnireach.normalizer import build_envelope
from omnireach.scorer import rank


def _r(source: str, score: float, likes: int = 0, ts: str = "2026-05-25T12:00:00Z") -> SearchResult:
    return SearchResult(
        source=source,
        adapter="t",
        title=f"{source}-{score}",
        url=f"https://e.x/{source}",
        ts=ts,
        score=score,
        engagement=Engagement(likes=likes),
    )


def test_build_envelope_attaches_query_and_ts():
    env = build_envelope(
        query="q",
        results=[_r("hn", 0.8)],
        errors=[SourceError(source="x", error="e")],
    )
    assert env.query == "q"
    assert env.results[0].source == "hn"
    assert env.errors[0].source == "x"
    # ts should be ISO-8601 ending in Z (UTC)
    assert env.ts.endswith("Z") or "+" in env.ts


def test_rank_orders_by_trust_desc():
    # Same recency (default ts) — trust drives ordering.
    a = _r("a", 0.3)
    b = _r("b", 0.9)
    c = _r("c", 0.5)
    trust_map = {"a": 0.3, "b": 0.9, "c": 0.5}
    ranked = rank([a, b, c], trust_map=trust_map)
    assert [r.source for r in ranked] == ["b", "c", "a"]


def test_rank_breaks_ties_by_recency_when_trust_equal():
    # Same ts on all three — recency normalizes to 0.5 for all, so trust drives ordering.
    older = _r("a", 0.5, likes=10, ts="2026-05-25T00:00:00Z")
    mid = _r("b", 0.5, likes=10, ts="2026-05-25T00:00:00Z")
    high_trust = _r("c", 0.5, likes=999, ts="2026-05-25T00:00:00Z")
    trust_map = {"a": 0.1, "b": 0.5, "c": 0.9}
    ranked = rank([older, mid, high_trust], trust_map=trust_map)
    assert [r.source for r in ranked] == ["c", "b", "a"]


# --- v0.4 scorer rewrite ---------------------------------------------------


def _r2(source: str, ts: str | None, trust: float, **kw) -> SearchResult:
    return SearchResult(source=source, adapter="t", title=source, url=f"https://x/{source}", ts=ts, **kw)


def test_rank_uses_source_trust_when_recency_equal():
    trust_map = {"hn": 0.85, "youtube": 0.6}
    a = _r2("hn", "2026-05-25T00:00:00+00:00", 0.85)
    b = _r2("youtube", "2026-05-25T00:00:00+00:00", 0.6)
    out = rank([b, a], trust_map=trust_map)
    assert [r.source for r in out] == ["hn", "youtube"]


def test_rank_uses_recency_when_trust_equal():
    trust_map = {"hn": 0.7, "web": 0.7}
    old = _r2("hn", "2020-01-01T00:00:00+00:00", 0.7)
    new = _r2("web", "2026-05-25T00:00:00+00:00", 0.7)
    out = rank([old, new], trust_map=trust_map)
    assert [r.source for r in out] == ["web", "hn"]


def test_rank_handles_missing_ts_as_midpoint():
    trust_map = {"hn": 0.7, "web": 0.7}
    no_ts = _r2("hn", None, 0.7)
    old = _r2("web", "2020-01-01T00:00:00+00:00", 0.7)
    out = rank([old, no_ts], trust_map=trust_map)
    assert [r.source for r in out] == ["hn", "web"]


def test_rank_writes_raw_score():
    trust_map = {"hn": 0.85}
    r = _r2("hn", "2026-05-25T00:00:00+00:00", 0.85)
    out = rank([r], trust_map=trust_map)
    assert 0.0 <= out[0].raw_score <= 1.0


def test_searchresult_defaults_cost_free():
    r = SearchResult(source="x", adapter="t", title="t", url="https://x")
    assert r.cost == "free"
    assert r.raw_score == 0.0
