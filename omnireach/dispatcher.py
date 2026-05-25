"""Dispatcher — concurrent fan-out across adapters, errors isolated."""

from __future__ import annotations

import asyncio

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult, SourceError


class Dispatcher:
    def __init__(self, *, timeout: float = 15.0, per_source_limit: int = 10) -> None:
        self.timeout = timeout
        self.per_source_limit = per_source_limit

    async def run(
        self, adapters: dict[str, AdapterBase], query: str
    ) -> tuple[list[SearchResult], list[SourceError]]:
        async def one(
            name: str, adapter: AdapterBase
        ) -> tuple[str, list[SearchResult] | SourceError]:
            try:
                results = await asyncio.wait_for(
                    adapter.search(query, limit=self.per_source_limit), timeout=self.timeout
                )
                return name, results
            except asyncio.TimeoutError:
                return name, SourceError(
                    source=name,
                    error=f"timeout (>{self.timeout:.1f}s)",
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
