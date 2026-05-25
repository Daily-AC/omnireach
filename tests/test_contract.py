import pytest
from pydantic import ValidationError

from omnireach.contract import SearchEnvelope, SearchResult, SourceError


def test_search_result_minimum_fields():
    r = SearchResult(
        source="hackernews",
        adapter="builtin",
        title="Show HN: omnireach",
        url="https://example.com/1",
        content="snippet",
        ts="2026-05-25T12:00:00Z",
        score=0.5,
    )
    assert r.source == "hackernews"
    assert r.engagement is None
    assert r.raw == {}


def test_search_result_rejects_unknown_source_type():
    with pytest.raises(ValidationError):
        SearchResult.model_validate(
            {"source": 123, "adapter": "builtin", "title": "x", "url": "x"}
        )


def test_search_envelope_roundtrip():
    env = SearchEnvelope(
        query="claude code",
        ts="2026-05-25T12:00:00Z",
        results=[
            SearchResult(
                source="hackernews",
                adapter="builtin",
                title="t",
                url="https://e.x/1",
                content="c",
                ts="2026-05-25T12:00:00Z",
                score=0.9,
            )
        ],
        errors=[SourceError(source="reddit", error="not configured")],
    )
    payload = env.model_dump_json()
    parsed = SearchEnvelope.model_validate_json(payload)
    assert parsed.results[0].title == "t"
    assert parsed.errors[0].source == "reddit"


def test_search_envelope_empty_results_is_valid():
    env = SearchEnvelope(query="q", ts="2026-05-25T12:00:00Z", results=[], errors=[])
    assert env.results == []
