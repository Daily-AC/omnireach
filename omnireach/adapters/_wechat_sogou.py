"""Sogou WeChat search using only HTTP and the Python standard library."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import quote_plus, urljoin, urlparse

import httpx

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
_TS_PATTERN = re.compile(r"timeConvert\('([0-9]+)'\)")
_URL_FRAGMENT_PATTERN = re.compile(r"url\s*\+=\s*'([^']*)'")
_VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})


def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
    return set((dict(attrs).get("class") or "").split())


class _SogouSerpParser(HTMLParser):
    """Narrow parser for Sogou result cards; avoids the 20MB lxml dependency."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.depth = 0
        self.news_list_depth: int | None = None
        self.item_depth: int | None = None
        self.item: dict[str, object] | None = None
        self.items: list[dict[str, object]] = []
        self.raw_parts: list[str] = []
        self.capture: str | None = None
        self.capture_depth: int | None = None

    def _captured_text(self, value: str) -> None:
        if self.item is None or self.capture is None:
            return
        parts = self.item.setdefault(self.capture, [])
        assert isinstance(parts, list)
        parts.append(value)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _VOID_TAGS:
            if self.item is not None:
                self.raw_parts.append(self.get_starttag_text())
            return
        self.depth += 1
        classes = _classes(attrs)
        if tag == "ul" and "news-list" in classes:
            self.news_list_depth = self.depth
        if (
            tag == "li"
            and self.news_list_depth is not None
            and self.item is None
        ):
            self.item_depth = self.depth
            self.item = {}
            self.raw_parts = []
        if self.item is not None:
            self.raw_parts.append(self.get_starttag_text())
            attrs_dict = dict(attrs)
            if tag == "a" and "_title_" in (attrs_dict.get("id") or ""):
                self.item["href"] = attrs_dict.get("href") or ""
                self.capture = "title_parts"
                self.capture_depth = self.depth
            elif tag == "p" and "txt-info" in classes:
                self.capture = "content_parts"
                self.capture_depth = self.depth
            elif tag == "span" and "all-time-y2" in classes:
                self.capture = "author_parts"
                self.capture_depth = self.depth
            elif tag == "script":
                self.capture = "script_parts"
                self.capture_depth = self.depth

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.item is not None:
            self.raw_parts.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        if self.item is not None:
            self.raw_parts.append(f"</{tag}>")
            if self.capture_depth == self.depth:
                self.capture = None
                self.capture_depth = None
            if self.item_depth == self.depth and tag == "li":
                self.item["item_html"] = "".join(self.raw_parts)
                self.items.append(self.item)
                self.item = None
                self.item_depth = None
                self.raw_parts = []
        if self.news_list_depth == self.depth and tag == "ul":
            self.news_list_depth = None
        self.depth = max(0, self.depth - 1)

    def handle_data(self, data: str) -> None:
        if self.item is not None:
            self.raw_parts.append(data)
            self._captured_text(data)

    def handle_entityref(self, name: str) -> None:
        raw = f"&{name};"
        if self.item is not None:
            self.raw_parts.append(raw)
            self._captured_text(html.unescape(raw))

    def handle_charref(self, name: str) -> None:
        raw = f"&#{name};"
        if self.item is not None:
            self.raw_parts.append(raw)
            self._captured_text(html.unescape(raw))

    def handle_comment(self, data: str) -> None:
        if self.item is not None:
            self.raw_parts.append(f"<!--{data}-->")


def _text(parts: object) -> str:
    if not isinstance(parts, list):
        return ""
    return " ".join("".join(str(part) for part in parts).split())


def _extract_wechat_url(link_page: str) -> str | None:
    """Reassemble the signed mp.weixin.qq.com URL emitted by Sogou JavaScript."""
    fragments = _URL_FRAGMENT_PATTERN.findall(link_page)
    if not fragments:
        return None
    candidate = "".join(fragments).replace("&amp;", "&").replace("@", "")
    parsed = urlparse(candidate)
    if parsed.scheme == "https" and parsed.hostname == "mp.weixin.qq.com":
        return candidate
    return None


def _raise_for_sogou_response(resp: object) -> None:
    status = int(getattr(resp, "status_code", 0))
    text = str(getattr(resp, "text", ""))
    if status >= 500:
        raise AdapterUnavailable("wechat:sogou", f"upstream {status}")
    if status in (403, 429):
        raise AdapterUnavailable(
            "wechat:sogou", f"rate-limited or blocked ({status})"
        )
    lower = text.lower()
    if "antispider" in lower or "人机验证" in text or "请输入验证码" in text:
        raise AdapterUnavailable(
            "wechat:sogou", "sogou anti-bot challenge served (captcha)"
        )


def parse_sogou_serp(html_text: str, *, limit: int) -> list[SearchResult]:
    parser = _SogouSerpParser()
    parser.feed(html_text)
    out: list[SearchResult] = []
    for item in parser.items[:limit]:
        href = str(item.get("href") or "")
        if not href:
            continue
        title = _text(item.get("title_parts"))
        content = _text(item.get("content_parts"))
        author = _text(item.get("author_parts")) or None
        script = _text(item.get("script_parts"))
        ts_iso: str | None = None
        match = _TS_PATTERN.search(script)
        if match:
            ts_iso = datetime.fromtimestamp(
                int(match.group(1)), tz=timezone.utc
            ).isoformat().replace("+00:00", "Z")
        url = urljoin(SOGOU_BASE + "/", href)
        out.append(SearchResult(
            source="wechat",
            adapter="sogou",
            title=title,
            url=url,
            content=content,
            author=author,
            ts=ts_iso,
            score=0.3,
            raw={
                "href": href,
                "account": author or "",
                "item_html": str(item.get("item_html") or ""),
            },
            cost="free",
        ))
    return out


async def search_sogou(
    query: str, *, limit: int = 10, timeout: float = 15.0
) -> list[SearchResult]:
    """Search and resolve Sogou redirect URLs while the session cookies are live."""
    search_url = SOGOU_BASE + SOGOU_SEARCH_PATH.format(q=quote_plus(query))
    try:
        with httpx.Client(
            headers=_CHROME_HEADERS,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            search_resp = client.get(search_url)
            _raise_for_sogou_response(search_resp)
            results = parse_sogou_serp(search_resp.text, limit=limit)
            for result in results:
                sogou_url = result.url
                try:
                    link_resp = client.get(
                        sogou_url, headers={"Referer": str(search_resp.url)}
                    )
                    _raise_for_sogou_response(link_resp)
                except (httpx.HTTPError, AdapterUnavailable):
                    continue
                direct_url = _extract_wechat_url(link_resp.text)
                if direct_url is None and _host_of_response(link_resp) == "mp.weixin.qq.com":
                    direct_url = str(link_resp.url)
                if direct_url:
                    result.raw["sogou_url"] = sogou_url
                    result.url = direct_url
            return results
    except AdapterUnavailable:
        raise
    except httpx.HTTPError as e:
        raise AdapterUnavailable("wechat:sogou", f"http error: {e}") from e


def _host_of_response(resp: object) -> str:
    return (urlparse(str(getattr(resp, "url", ""))).hostname or "").lower()
