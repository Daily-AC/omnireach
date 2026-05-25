from pathlib import Path

import httpx
import respx

from omnireach.adapters.hackernews import HackerNewsAdapter


def _load(name: str) -> str:
    return (Path(__file__).parent.parent / "fixtures" / name).read_text()


@respx.mock
async def test_hn_search_returns_normalized_results():
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(200, text=_load("hn_algolia_search.json"))
    )

    a = HackerNewsAdapter()
    results = await a.search("claude", limit=5)

    assert len(results) == 2
    matched = next(r for r in results if "Claude 4.7" in r.title)
    assert matched.source == "hackernews"
    assert matched.adapter == "builtin"
    assert matched.url == "https://example.com/post-1"
    assert matched.author == "alice"
    assert matched.engagement is not None
    assert matched.engagement.likes == 250
    assert matched.engagement.comments == 88


@respx.mock
async def test_hn_search_passes_query_and_limit():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        return httpx.Response(200, text=_load("hn_algolia_search.json"))

    respx.get("https://hn.algolia.com/api/v1/search").mock(side_effect=handler)

    a = HackerNewsAdapter()
    await a.search("omnireach", limit=3)

    assert "query=omnireach" in captured["url"]
    assert "hitsPerPage=3" in captured["url"]
    assert "tags=story" in captured["url"]


@respx.mock
async def test_hn_search_falls_back_to_hn_url_when_url_missing():
    """Ask-HN posts have no external URL — must build news.ycombinator.com link."""
    fixture = """{"hits": [{"objectID": "42", "title": "Ask HN: foo", "url": null,
                 "author": "alice", "created_at_i": 1748160000, "points": 10, "num_comments": 2}]}"""
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(200, text=fixture)
    )

    a = HackerNewsAdapter()
    results = await a.search("ask", limit=5)
    assert results[0].url == "https://news.ycombinator.com/item?id=42"


async def test_hn_is_ready_does_not_call_network():
    a = HackerNewsAdapter()
    assert await a.is_ready() is True
