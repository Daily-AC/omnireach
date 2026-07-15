"""Dispatcher — concurrent fan-out across adapters, errors isolated."""

from __future__ import annotations

import asyncio

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult, SourceError


class Dispatcher:
    def __init__(
        self,
        *,
        timeout: float = 15.0,
        per_source_limit: int = 10,
        timeouts_by_source: dict[str, float | None] | None = None,
    ) -> None:
        self.timeout = timeout
        self.per_source_limit = per_source_limit
        self.timeouts_by_source = timeouts_by_source or {}

    def _resolved_timeout(self, source_id: str) -> float:
        t = self.timeouts_by_source.get(source_id)
        return t if t is not None else self.timeout

    async def run(
        self, adapters: dict[str, AdapterBase], query: str
    ) -> tuple[list[SearchResult], list[SourceError]]:
        async def one(
            name: str, adapter: AdapterBase
        ) -> tuple[str, list[SearchResult] | SourceError]:
            resolved = self._resolved_timeout(name)
            try:
                results = await asyncio.wait_for(
                    adapter.search(query, limit=self.per_source_limit), timeout=resolved
                )
                return name, results
            except asyncio.TimeoutError:
                hint = ""
                if name in {
                    "google", "reddit", "twitter", "xiaohongshu", "tiktok", "douyin"
                }:
                    hint = (
                        "; browser-backed source may be cold-starting, "
                        "retry with a larger --timeout"
                    )
                return name, SourceError(
                    source=name,
                    error=f"timeout (>{resolved:.1f}s){hint}",
                    category="failed",
                )
            except AdapterUnavailable as e:
                return name, SourceError(
                    source=name, error=str(e), category="unavailable"
                )
            except Exception as e:  # noqa: BLE001
                return name, SourceError(source=name, error=str(e), category="failed")

        outputs = await asyncio.gather(*[one(n, a) for n, a in adapters.items()])

        all_results: list[SearchResult] = []
        errors: list[SourceError] = []
        for _name, payload in outputs:
            if isinstance(payload, list):
                all_results.extend(payload)
            else:
                errors.append(payload)
        return all_results, errors
