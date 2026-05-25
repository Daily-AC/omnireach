import asyncio

import pytest

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult
from omnireach.dispatcher import Dispatcher


def _result(source: str) -> SearchResult:
    return SearchResult(
        source=source,
        adapter="t",
        title=f"hit-{source}",
        url=f"https://e.x/{source}",
        ts="2026-05-25T12:00:00Z",
        score=0.5,
    )


class OkAdapter(AdapterBase):
    name = "ok"

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        return [_result(self.name)]


class SlowAdapter(OkAdapter):
    name = "slow"

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        await asyncio.sleep(5)
        return [_result("slow")]


class BoomAdapter(OkAdapter):
    name = "boom"

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        raise AdapterUnavailable("boom", "exploded", hint="reinstall")


async def test_dispatch_aggregates_results():
    d = Dispatcher(timeout=1.0)
    a1 = OkAdapter(); a1.name = "a1"
    a2 = OkAdapter(); a2.name = "a2"
    out, errs = await d.run({"a1": a1, "a2": a2}, "q")
    sources = sorted(r.source for r in out)
    assert sources == ["a1", "a2"]
    assert errs == []


async def test_dispatch_isolates_failures():
    d = Dispatcher(timeout=1.0)
    a = OkAdapter(); a.name = "ok"
    out, errs = await d.run({"ok": a, "boom": BoomAdapter()}, "q")
    assert any(r.source == "ok" for r in out)
    assert any(e.source == "boom" for e in errs)


async def test_dispatch_times_out_one_source_without_blocking_others():
    d = Dispatcher(timeout=0.1)
    a = OkAdapter(); a.name = "ok"
    out, errs = await d.run({"ok": a, "slow": SlowAdapter()}, "q")
    assert any(r.source == "ok" for r in out)
    assert any(e.source == "slow" and "timeout" in e.error.lower() for e in errs)
