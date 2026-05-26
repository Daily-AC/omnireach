"""B站官方 search API backend — free fallback for bilibili adapter (v0.9).

Used by omnireach/adapters/bilibili.py when EXA_API_KEY is absent or Exa
upstream is unavailable. Pure httpx + json; no cookie, no auth, but the
upstream requires a `Referer: https://search.bilibili.com/` header to
serve results.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx

from omnireach.adapters.base import AdapterUnavailable
from omnireach.contract import Engagement, SearchResult

BILI_SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/all/v2"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Referer": "https://search.bilibili.com/",
    "Accept": "application/json",
}

_EM_TAG = re.compile(r'<em class="keyword">(.*?)</em>')


def _strip_em(s: str) -> str:
    """B站 titles wrap matched keywords in <em class="keyword">…</em>."""
    return _EM_TAG.sub(r"\1", s or "")


def _ts_iso(unix_ts: Any) -> str | None:
    if not isinstance(unix_ts, (int, float)) or unix_ts <= 0:
        return None
    return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def parse_bilibili_response(payload: dict, *, limit: int) -> list[SearchResult]:
    """Pure parser — extract video block hits from the search/all/v2 response."""
    if not isinstance(payload, dict) or payload.get("code") != 0:
        return []
    data = payload.get("data") or {}
    blocks = data.get("result") or []
    videos: list[dict] = []
    for block in blocks:
        if isinstance(block, dict) and block.get("result_type") == "video":
            videos = block.get("data") or []
            break

    out: list[SearchResult] = []
    for item in videos[:limit]:
        bvid = item.get("bvid") or ""
        url = f"https://www.bilibili.com/video/{bvid}" if bvid else (item.get("arcurl") or "")
        out.append(
            SearchResult(
                source="bilibili",
                adapter="bilibili-api",
                title=_strip_em(item.get("title") or ""),
                url=url,
                content=item.get("description") or "",
                author=item.get("author") or None,
                ts=_ts_iso(item.get("pubdate")),
                score=0.4,
                engagement=Engagement(
                    likes=item.get("like"),
                    views=item.get("play"),
                    comments=item.get("review"),
                ),
                raw=item,
                cost="free",
            )
        )
    return out


async def search_bilibili(query: str, *, limit: int = 10, timeout: float = 15.0) -> list[SearchResult]:
    """Public entry point used by bilibili orchestrator."""
    try:
        with httpx.Client(headers=_HEADERS, timeout=timeout) as c:
            resp = c.get(BILI_SEARCH_URL, params={"keyword": query})
    except httpx.HTTPError as e:
        raise AdapterUnavailable("bilibili:api", f"http error: {e}") from e
    if resp.status_code == 412 or resp.status_code == 403:
        raise AdapterUnavailable("bilibili:api", f"blocked or risk-controlled ({resp.status_code})")
    if resp.status_code == 429:
        raise AdapterUnavailable("bilibili:api", "rate-limited (429)")
    if resp.status_code >= 500:
        raise AdapterUnavailable("bilibili:api", f"upstream {resp.status_code}")
    try:
        payload = resp.json()
    except ValueError as e:
        raise AdapterUnavailable("bilibili:api", f"non-JSON response: {e}") from e
    # B站 error codes: -412 risk control, -101 not logged in, etc.
    code = payload.get("code")
    if code and code != 0:
        raise AdapterUnavailable("bilibili:api", f"upstream error code={code} msg={payload.get('message')!r}")
    return parse_bilibili_response(payload, limit=limit)
