"""Scorer — rank results across sources by recency + source_trust."""

from __future__ import annotations

from datetime import datetime

from omnireach.contract import SearchResult

W_RECENCY = 0.4
W_TRUST = 0.6


def _ts_to_epoch(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _normalize_recency(results: list[SearchResult]) -> list[float]:
    epochs = [_ts_to_epoch(r.ts) for r in results]
    real = [e for e in epochs if e is not None]
    if not real:
        return [0.5] * len(results)
    lo, hi = min(real), max(real)
    span = hi - lo if hi > lo else 1.0
    return [0.5 if e is None else (e - lo) / span for e in epochs]


def rank(results: list[SearchResult], *, trust_map: dict[str, float] | None = None) -> list[SearchResult]:
    trust_map = trust_map or {}
    rec = _normalize_recency(results)
    for r, rn in zip(results, rec, strict=True):
        t = trust_map.get(r.source, 0.7)
        r.raw_score = W_RECENCY * rn + W_TRUST * t
    return sorted(results, key=lambda r: -r.raw_score)
