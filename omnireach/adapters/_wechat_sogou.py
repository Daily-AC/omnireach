"""Sogou 微信搜索 backend — free fallback for wechat adapter (v0.9).

Used by omnireach/adapters/wechat.py when EXA_API_KEY is absent or Exa
upstream is unavailable. HTTP-only via httpx + lxml; no cookie / no auth.

If `scrapling` is installed, the backend uses Scrapling's StealthyFetcher
as an optional anti-detection enhancement; otherwise falls back to plain
httpx with a Chrome User-Agent.
"""

from __future__ import annotations

import re
from urllib.parse import quote_plus, urljoin

import httpx
from lxml import html as lxml_html

from omnireach.adapters.base import AdapterUnavailable
from omnireach.contract import SearchResult

SOGOU_BASE = "https://weixin.sogou.com"
SOGOU_SEARCH_PATH = "/weixin?type=2&query={q}&ie=utf8"

_CHROME_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

_TS_PATTERN = re.compile(r"timeConvert\('(\d+)'\)")

# Scrapling optional import — see spec §3.3
try:
    from scrapling.fetchers import StealthyFetcher  # type: ignore
    _STEALTHY = StealthyFetcher
except ImportError:
    _STEALTHY = None


def _fetch(url: str, *, timeout: float = 15.0) -> str:
    """Fetch Sogou page; use Scrapling stealth if available, else httpx."""
    if _STEALTHY is not None:
        # Scrapling StealthyFetcher returns a Response-like with .body attr
        try:
            resp = _STEALTHY.fetch(url, timeout=int(timeout), headless=True)
            if getattr(resp, "status", 200) >= 400:
                raise AdapterUnavailable("wechat:sogou", f"upstream {resp.status}")
            return resp.body if isinstance(resp.body, str) else resp.body.decode("utf-8", errors="replace")
        except AdapterUnavailable:
            raise
        except Exception as e:  # noqa: BLE001 — Scrapling exceptions vary
            raise AdapterUnavailable("wechat:sogou", f"scrapling error: {e}") from e

    try:
        with httpx.Client(
            headers=_CHROME_HEADERS,
            timeout=timeout,
            follow_redirects=True,
        ) as c:
            resp = c.get(url)
    except httpx.HTTPError as e:
        raise AdapterUnavailable("wechat:sogou", f"http error: {e}") from e
    if resp.status_code >= 500:
        raise AdapterUnavailable("wechat:sogou", f"upstream {resp.status_code}")
    if resp.status_code in (403, 429):
        raise AdapterUnavailable("wechat:sogou", f"rate-limited or blocked ({resp.status_code})")
    if "antispider" in resp.text.lower() or "人机验证" in resp.text or "请输入验证码" in resp.text:
        raise AdapterUnavailable("wechat:sogou", "sogou anti-bot challenge served (captcha)")
    return resp.text


def parse_sogou_serp(html_text: str, *, limit: int) -> list[SearchResult]:
    """Pure parser — extracted so unit tests can hit it without HTTP."""
    doc = lxml_html.fromstring(html_text)
    items = doc.cssselect(".news-list li")
    out: list[SearchResult] = []
    for item in items[:limit]:
        title_a = item.cssselect(".txt-box h3 a")
        if not title_a:
            continue
        title = title_a[0].text_content().strip()
        href = title_a[0].get("href", "")
        url = urljoin(SOGOU_BASE + "/", href) if href else ""

        snippet_p = item.cssselect(".txt-box p.txt-info")
        content = snippet_p[0].text_content().strip() if snippet_p else ""

        account_el = item.cssselect(".s-p .all-time-y2")
        author = account_el[0].text_content().strip() if account_el else None

        ts_script = item.cssselect(".s-p .s2 script")
        ts_iso: str | None = None
        if ts_script:
            m = _TS_PATTERN.search(ts_script[0].text_content() or "")
            if m:
                from datetime import datetime, timezone
                ts_iso = datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc).isoformat().replace("+00:00", "Z")

        # raw preserves the original item HTML for downstream inspection
        item_html = lxml_html.tostring(item, encoding="unicode")
        raw = {
            "title_html": lxml_html.tostring(title_a[0], encoding="unicode") if title_a else "",
            "href": href,
            "snippet_html": lxml_html.tostring(snippet_p[0], encoding="unicode") if snippet_p else "",
            "account": author or "",
            "item_html": item_html,
        }

        out.append(
            SearchResult(
                source="wechat",
                adapter="sogou",
                title=title,
                url=url,
                content=content,
                author=author or None,
                ts=ts_iso,
                score=0.3,
                raw=raw,
                cost="free",
            )
        )
    return out


async def search_sogou(query: str, *, limit: int = 10, timeout: float = 15.0) -> list[SearchResult]:
    """Public entry point used by wechat orchestrator."""
    url = SOGOU_BASE + SOGOU_SEARCH_PATH.format(q=quote_plus(query))
    html_text = _fetch(url, timeout=timeout)
    return parse_sogou_serp(html_text, limit=limit)
