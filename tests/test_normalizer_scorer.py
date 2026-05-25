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


def test_rank_orders_by_score_desc():
    a = _r("a", 0.3)
    b = _r("b", 0.9)
    c = _r("c", 0.5)
    ranked = rank([a, b, c])
    assert [r.source for r in ranked] == ["b", "c", "a"]


def test_rank_breaks_ties_by_engagement_then_recency():
    older = _r("a", 0.5, likes=10, ts="2026-01-01T00:00:00Z")
    newer = _r("b", 0.5, likes=10, ts="2026-05-25T00:00:00Z")
    more_liked = _r("c", 0.5, likes=999, ts="2026-01-01T00:00:00Z")
    ranked = rank([older, newer, more_liked])
    assert [r.source for r in ranked] == ["c", "b", "a"]
