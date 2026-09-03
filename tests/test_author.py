"""Creator-catalog service: the dimension keyword search cannot answer."""

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.author import author_catalog
from omnireach.contract import AuthorIdentity, Engagement, SearchResult

SEC_UID = "MS4wLjABAAAAAAKy2_R6k-oFWT5E-97gbGZQ1laaweQMWImJDkDaef0"


def _identity(**overrides) -> AuthorIdentity:
    return AuthorIdentity(**{
        "source": "douyin",
        "handle": "彭十六",
        "id": SEC_UID,
        "name": "彭十六elf",
        "url": f"https://www.douyin.com/user/{SEC_UID}",
        "followers": 28195000,
        "resolved_from": "search",
        **overrides,
    })


def _result(index: int, likes: int) -> SearchResult:
    return SearchResult(
        source="douyin",
        adapter="native-chrome",
        title=f"work {index}",
        url=f"https://www.douyin.com/video/{index}",
        engagement=Engagement(likes=likes),
    )


class _StubAdapter:
    def __init__(self, identity, results, stats, error=None):
        self._payload = (identity, results, stats)
        self._error = error
        self.calls = []

    async def is_ready(self):
        return True

    async def search(self, query, *, limit=10):
        raise AssertionError("author must not fall back to keyword search")

    async def author(self, handle, **kwargs):
        self.calls.append({"handle": handle, **kwargs})
        if self._error is not None:
            raise self._error
        return self._payload


def _install(monkeypatch, adapter):
    class _Spec:
        def load_adapter_class(self):
            return lambda: adapter

    class _Registry:
        def get(self, source_id):
            assert source_id == "douyin"
            return _Spec()

    monkeypatch.setattr("omnireach.author.load_registry", lambda: _Registry())


async def test_catalog_envelope_carries_identity_and_scan_stats(monkeypatch):
    adapter = _StubAdapter(
        _identity(),
        [_result(1, 30), _result(2, 10)],
        {"order": "recent", "scanned": 355, "complete": True, "pages": 83},
    )
    _install(monkeypatch, adapter)

    envelope = await author_catalog("彭十六", limit=2)

    assert envelope.query == "彭十六"
    assert envelope.author.id == SEC_UID
    assert envelope.author.url.endswith(SEC_UID)
    assert envelope.scanned == 355
    assert envelope.complete is True
    assert [result.url for result in envelope.results] == [
        "https://www.douyin.com/video/1",
        "https://www.douyin.com/video/2",
    ]
    assert envelope.errors == []
    assert adapter.calls == [{
        "handle": "彭十六",
        "limit": 2,
        "order": "recent",
        "include_media_urls": False,
        "timeout": 180.0,
    }]


async def test_nickname_resolution_is_reported_as_a_warning(monkeypatch):
    _install(monkeypatch, _StubAdapter(
        _identity(),
        [_result(1, 30)],
        {"order": "recent", "scanned": 1, "complete": True, "pages": 1},
    ))

    envelope = await author_catalog("彭十六")

    assert any("by follower count" in warning for warning in envelope.warnings)


async def test_url_resolution_is_not_warned_about(monkeypatch):
    _install(monkeypatch, _StubAdapter(
        _identity(resolved_from="url"),
        [_result(1, 30)],
        {"order": "recent", "scanned": 1, "complete": True, "pages": 1},
    ))

    envelope = await author_catalog(f"https://www.douyin.com/user/{SEC_UID}")

    assert envelope.warnings == []


async def test_incomplete_like_ranking_says_so(monkeypatch):
    """A truncated scan makes "top by likes" a claim the data cannot support."""
    _install(monkeypatch, _StubAdapter(
        _identity(resolved_from="url"),
        [_result(1, 30)],
        {"order": "likes", "scanned": 120, "complete": False, "pages": 30},
    ))

    envelope = await author_catalog(
        f"https://www.douyin.com/user/{SEC_UID}", order="likes",
    )

    assert envelope.complete is False
    assert any("may be\nincomplete" in w or "incomplete" in w for w in envelope.warnings)
    assert any("120 works" in warning for warning in envelope.warnings)


async def test_unavailable_bridge_becomes_a_structured_error(monkeypatch):
    _install(monkeypatch, _StubAdapter(
        None, None, None,
        error=AdapterUnavailable(
            "douyin",
            "the connected Chrome extension does not implement douyin.author",
            hint="run `omnireach bridge install`, then reload the extension",
        ),
    ))

    envelope = await author_catalog("彭十六")

    assert envelope.results == []
    assert len(envelope.errors) == 1
    assert envelope.errors[0].category == "unavailable"
    assert "reload the extension" in envelope.errors[0].error


async def test_adapter_crash_becomes_a_structured_error(monkeypatch):
    _install(monkeypatch, _StubAdapter(
        None, None, None, error=RuntimeError("Douyin catalog API answered status_code 8"),
    ))

    envelope = await author_catalog("彭十六")

    assert envelope.errors[0].category == "failed"
    assert "status_code 8" in envelope.errors[0].error


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"source": "youtube"}, "has no creator catalog"),
        ({"limit": 0}, "between 1 and 200"),
        ({"limit": 201}, "between 1 and 200"),
        ({"order": "oldest"}, "recent or likes"),
    ],
)
async def test_invalid_arguments_raise_before_touching_chrome(kwargs, message):
    with pytest.raises(ValueError, match=message):
        await author_catalog("彭十六", **kwargs)


async def test_blank_handle_is_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        await author_catalog("   ")
