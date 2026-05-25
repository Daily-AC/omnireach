"""Scorer — rank results across sources by recency + source_trust."""

from __future__ import annotations

from datetime import datetime

from omnireach.contract import SearchResult

W_RECENCY = 0.4
W_TRUST = 0.6
assert W_RECENCY + W_TRUST == 1.0, "scorer weights must sum to 1.0"


def _ts_to_epoch(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _normalize_recency(results: list[SearchResult]) -> list[float]:
    """Normalize timestamps to [0, 1] by linear scaling between min and max epoch.

    None timestamps default to 0.5 (treated as "unknown / mid-range") so they
    don't lose to the only present timestamp, which would be 0.0 after
    normalization. If all timestamps are None, every entry gets 0.5.
    """
    epochs = [_ts_to_epoch(r.ts) for r in results]
    real = [e for e in epochs if e is not None]
    if not real:
        return [0.5] * len(results)
    lo, hi = min(real), max(real)
    span = hi - lo if hi > lo else 1.0
    return [0.5 if e is None else (e - lo) / span for e in epochs]


def rank(results: list[SearchResult], *, trust_map: dict[str, float] | None = None) -> list[SearchResult]:
    """Compute raw_score = 0.4*recency_norm + 0.6*source_trust and return sorted desc. Mutates each result's raw_score in place."""
    trust_map = trust_map or {}
    rec = _normalize_recency(results)
    for r, rn in zip(results, rec, strict=True):
        t = trust_map.get(r.source, 0.7)
        r.raw_score = W_RECENCY * rn + W_TRUST * t
    return sorted(results, key=lambda r: -r.raw_score)
