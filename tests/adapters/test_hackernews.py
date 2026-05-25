import json
from pathlib import Path

import httpx
import pytest
import respx

from omnireach.adapters.hackernews import HackerNewsAdapter


def _load(name: str) -> str:
    return (Path(__file__).parent.parent / "fixtures" / name).read_text()


@respx.mock
async def test_hn_search_returns_normalized_results():
    respx.get("https://hacker-news.firebaseio.com/v0/topstories.json").mock(
        return_value=httpx.Response(200, text=_load("hn_topstories.json"))
    )
    respx.get("https://hacker-news.firebaseio.com/v0/item/1.json").mock(
        return_value=httpx.Response(200, text=_load("hn_item_1.json"))
    )
    respx.get("https://hacker-news.firebaseio.com/v0/item/2.json").mock(
        return_value=httpx.Response(200, text=_load("hn_item_2.json"))
    )

    a = HackerNewsAdapter()
    results = await a.search("claude", limit=5)

    titles = [r.title for r in results]
    assert any("Claude 4.7" in t for t in titles)
    matched = next(r for r in results if "Claude 4.7" in r.title)
    assert matched.source == "hackernews"
    assert matched.adapter == "builtin"
    assert matched.url == "https://example.com/post-1"
    assert matched.engagement is not None
    assert matched.engagement.likes == 250
    assert matched.engagement.comments == 88


@respx.mock
async def test_hn_search_filters_by_query():
    respx.get("https://hacker-news.firebaseio.com/v0/topstories.json").mock(
        return_value=httpx.Response(200, text=_load("hn_topstories.json"))
    )
    respx.get("https://hacker-news.firebaseio.com/v0/item/1.json").mock(
        return_value=httpx.Response(200, text=_load("hn_item_1.json"))
    )
    respx.get("https://hacker-news.firebaseio.com/v0/item/2.json").mock(
        return_value=httpx.Response(200, text=_load("hn_item_2.json"))
    )

    a = HackerNewsAdapter()
    results = await a.search("omnireach", limit=5)
    assert len(results) == 1
    assert "omnireach" in results[0].title.lower()


async def test_hn_is_ready_does_not_call_network():
    a = HackerNewsAdapter()
    assert await a.is_ready() is True
