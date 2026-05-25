"""Normalizer — wraps adapter outputs into a SearchEnvelope."""

from __future__ import annotations

from datetime import datetime, timezone

from omnireach.contract import SearchEnvelope, SearchResult, SourceError


def build_envelope(
    *, query: str, results: list[SearchResult], errors: list[SourceError]
) -> SearchEnvelope:
    return SearchEnvelope(
        query=query,
        ts=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        results=results,
        errors=errors,
    )
