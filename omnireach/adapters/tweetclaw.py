"""TweetClaw / Xquik X search booster."""

from __future__ import annotations

import os
from typing import Any

import httpx

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult

DEFAULT_XQUIK_BASE_URL = "https://xquik.com"
TWEET_SEARCH_PATH = "/api/v1/x/tweets/search"


def _base_url() -> str:
    value = os.environ.get("XQUIK_BASE_URL", DEFAULT_XQUIK_BASE_URL).strip()
    return value.rstrip("/") or DEFAULT_XQUIK_BASE_URL


def _extract_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("results", "tweets", "data", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    nested = data.get("data")
    if isinstance(nested, dict):
        return _extract_items(nested)
    return []


def _text(item: dict[str, Any]) -> str:
    value = item.get("text") or item.get("content") or item.get("full_text") or ""
    return value if isinstance(value, str) else str(value)


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def _first_present(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in item:
            return item[key]
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return None


def _author(item: dict[str, Any]) -> str | None:
    author = item.get("author")
    if isinstance(author, dict):
        return _str_or_none(author.get("username") or author.get("handle") or author.get("screenName"))
    return _str_or_none(author or item.get("username") or item.get("screen_name"))


def _tweet_url(item: dict[str, Any]) -> str:
    direct = item.get("url") or item.get("tweet_url")
    if isinstance(direct, str) and direct:
        return direct
    tweet_id = item.get("id") or item.get("tweet_id")
    author = _author(item)
    if tweet_id and author:
        handle = str(author).lstrip("@")
        return f"https://x.com/{handle}/status/{tweet_id}"
    return ""


class TweetClawAdapter(AdapterBase):
    name = "tweetclaw"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bool(os.environ.get("XQUIK_API_KEY"))

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        key = os.environ.get("XQUIK_API_KEY")
        if not key:
            raise AdapterUnavailable(
                "tweetclaw",
                "XQUIK_API_KEY 未设置",
                hint="omnireach setup tweetclaw",
            )

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "omnireach-tweetclaw-adapter",
        }
        params = {"q": query, "limit": str(limit)}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"{_base_url()}{TWEET_SEARCH_PATH}",
                    headers=headers,
                    params=params,
                )
            except httpx.HTTPError as e:
                raise AdapterUnavailable("tweetclaw", f"http error: {e}") from e

        if resp.status_code in (401, 403):
            raise AdapterUnavailable("tweetclaw", f"API key rejected ({resp.status_code})")
        if resp.status_code == 429:
            raise AdapterUnavailable("tweetclaw", "rate limited (429)")
        if resp.status_code >= 500:
            raise AdapterUnavailable("tweetclaw", f"upstream {resp.status_code}")

        items = _extract_items(resp.json())[:limit]
        results: list[SearchResult] = []
        for item in items:
            text = _text(item)
            title = text[:80] + "..." if len(text) > 80 else text
            results.append(
                SearchResult(
                    source="tweetclaw",
                    adapter="xquik-api",
                    title=title,
                    url=_tweet_url(item),
                    content=text,
                    author=_author(item),
                    ts=_str_or_none(item.get("created_at") or item.get("createdAt")),
                    score=0.65,
                    engagement=Engagement(
                        likes=_int_or_none(_first_present(item, ("likeCount", "like_count", "likes"))),
                        shares=_int_or_none(_first_present(item, ("retweetCount", "retweet_count", "retweets"))),
                        comments=_int_or_none(_first_present(item, ("replyCount", "reply_count", "replies"))),
                        views=_int_or_none(_first_present(item, ("viewCount", "view_count", "views"))),
                    ),
                    cost="paid",
                    raw=item,
                )
            )
        return results
