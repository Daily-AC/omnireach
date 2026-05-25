"""Scorer — rank results across sources."""

from __future__ import annotations

from datetime import datetime

from omnireach.contract import SearchResult


def _ts_to_epoch(ts: str | None) -> float:
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def rank(results: list[SearchResult]) -> list[SearchResult]:
    """Sort by score desc, breaking ties with engagement.likes then ts (newer first)."""

    def key(r: SearchResult) -> tuple[float, int, float]:
        likes = (r.engagement.likes if r.engagement and r.engagement.likes else 0)
        return (-r.score, -likes, -_ts_to_epoch(r.ts))

    return sorted(results, key=key)
