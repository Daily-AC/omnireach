import pytest

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult


class DummyAdapter(AdapterBase):
    name = "dummy"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        return [
            SearchResult(
                source="dummy",
                adapter="dummy",
                title=f"hit for {query}",
                url="https://e.x/1",
                content="x",
                ts="2026-05-25T12:00:00Z",
                score=0.5,
            )
        ]


async def test_dummy_adapter_search():
    a = DummyAdapter()
    out = await a.search("hello")
    assert len(out) == 1
    assert out[0].title == "hit for hello"


async def test_base_cannot_instantiate():
    with pytest.raises(TypeError):
        AdapterBase()  # type: ignore[abstract]


def test_adapter_unavailable_carries_hint():
    exc = AdapterUnavailable("dummy", "agent-reach not installed", hint="pipx install agent-reach")
    assert "agent-reach" in str(exc)
    assert exc.hint == "pipx install agent-reach"
