import asyncio

from omnireach.adapters._opencli import OpenCLICommandError
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
    a1 = OkAdapter()
    a1.name = "a1"
    a2 = OkAdapter()
    a2.name = "a2"
    out, errs = await d.run({"a1": a1, "a2": a2}, "q")
    sources = sorted(r.source for r in out)
    assert sources == ["a1", "a2"]
    assert errs == []


async def test_dispatch_isolates_failures():
    d = Dispatcher(timeout=1.0)
    a = OkAdapter()
    a.name = "ok"
    out, errs = await d.run({"ok": a, "boom": BoomAdapter()}, "q")
    assert any(r.source == "ok" for r in out)
    assert any(e.source == "boom" for e in errs)


async def test_dispatch_times_out_one_source_without_blocking_others():
    d = Dispatcher(timeout=0.1)
    a = OkAdapter()
    a.name = "ok"
    out, errs = await d.run({"ok": a, "slow": SlowAdapter()}, "q")
    assert any(r.source == "ok" for r in out)
    assert any(e.source == "slow" and "timeout" in e.error.lower() for e in errs)


# --- v0.6 T1: SourceError.category classification ---


class _CatOkAdapter(AdapterBase):
    name = "ok"

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        return [SearchResult(source="ok", adapter="t", title="x", url="https://x")]


class _CatUnavailableAdapter(AdapterBase):
    name = "u"

    async def is_ready(self) -> bool:
        return False

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        raise AdapterUnavailable("u", "missing key")


class _CatFailedAdapter(AdapterBase):
    name = "f"

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        raise ValueError("kaboom")


class _OpenCLIFailedAdapter(AdapterBase):
    name = "douyin"

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        raise OpenCLICommandError("douyin", "Chrome bridge disconnected")


def test_dispatcher_classifies_unavailable():
    d = Dispatcher(timeout=5.0, per_source_limit=5)
    results, errors = asyncio.run(d.run({"u": _CatUnavailableAdapter()}, "q"))
    assert results == []
    assert len(errors) == 1
    assert errors[0].category == "unavailable"


def test_dispatcher_classifies_failed():
    d = Dispatcher(timeout=5.0, per_source_limit=5)
    results, errors = asyncio.run(d.run({"f": _CatFailedAdapter()}, "q"))
    assert len(errors) == 1
    assert errors[0].category == "failed"


def test_dispatcher_classifies_opencli_command_error_as_failed():
    results, errors = asyncio.run(
        Dispatcher(timeout=5.0).run(
            {"douyin": _OpenCLIFailedAdapter()}, "q"
        )
    )
    assert results == []
    assert errors[0].category == "failed"
    assert "Chrome bridge disconnected" in errors[0].error


def test_dispatcher_classifies_timeout_as_failed():
    class _CatSlow(AdapterBase):
        name = "slow"

        async def is_ready(self) -> bool:
            return True

        async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
            await asyncio.sleep(2)
            return []

    d = Dispatcher(timeout=0.1, per_source_limit=5)
    results, errors = asyncio.run(d.run({"slow": _CatSlow()}, "q"))
    assert len(errors) == 1
    assert errors[0].category == "failed"
    assert "timeout" in errors[0].error.lower()


def test_dispatcher_keeps_successful_results_alongside_errors():
    d = Dispatcher(timeout=5.0, per_source_limit=5)
    results, errors = asyncio.run(
        d.run(
            {
                "ok": _CatOkAdapter(),
                "u": _CatUnavailableAdapter(),
                "f": _CatFailedAdapter(),
            },
            "q",
        )
    )
    assert len(results) == 1
    assert len(errors) == 2
    categories = {e.source: e.category for e in errors}
    assert categories["u"] == "unavailable"
    assert categories["f"] == "failed"


def test_dispatcher_uses_per_source_timeout():
    import asyncio
    from omnireach.adapters.base import AdapterBase
    from omnireach.dispatcher import Dispatcher

    class _Slow(AdapterBase):
        name = "slow"
        async def is_ready(self):
            return True
        async def search(self, q, *, limit=10):
            await asyncio.sleep(2)
            return []

    d = Dispatcher(timeout=10.0, per_source_limit=5,
                   timeouts_by_source={"slow": 0.1})
    results, errors = asyncio.run(d.run({"slow": _Slow()}, "q"))
    assert len(errors) == 1
    assert errors[0].category == "failed"
    assert "timeout" in errors[0].error.lower()


def test_dispatcher_falls_back_to_global_timeout_when_per_source_missing():
    import asyncio
    from omnireach.adapters.base import AdapterBase
    from omnireach.dispatcher import Dispatcher

    class _Slow(AdapterBase):
        name = "slow"
        async def is_ready(self):
            return True
        async def search(self, q, *, limit=10):
            await asyncio.sleep(2)
            return []

    d = Dispatcher(timeout=0.1, per_source_limit=5, timeouts_by_source={})
    results, errors = asyncio.run(d.run({"slow": _Slow()}, "q"))
    assert len(errors) == 1
    assert errors[0].category == "failed"
