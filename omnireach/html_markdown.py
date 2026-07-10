"""Small dependency-free HTML to Markdown extractor for ordinary web pages."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin


_IGNORED_TAGS = frozenset({
    "aside", "footer", "form", "header", "nav", "noscript", "script",
    "style", "svg", "template",
})
_BLOCK_TAGS = frozenset({
    "address", "article", "div", "figure", "figcaption", "main", "p",
    "section", "table", "tr",
})
_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})


class _MarkdownParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.full: list[str] = []
        self.focused: list[str] = []
        self.title: list[str] = []
        self.ignore_depth = 0
        self.focus_depth = 0
        self.title_depth = 0
        self.pre_depth = 0
        self.links: list[str | None] = []

    def _append(self, value: str) -> None:
        self.full.append(value)
        if self.focus_depth:
            self.focused.append(value)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.ignore_depth:
            if tag not in _VOID_TAGS:
                self.ignore_depth += 1
            return
        if tag in _IGNORED_TAGS:
            self.ignore_depth = 1
            return
        if tag == "title":
            self.title_depth = 1
            return
        if self.title_depth:
            if tag not in _VOID_TAGS:
                self.title_depth += 1
            return
        if tag in ("article", "main"):
            self.focus_depth += 1
        if tag in _BLOCK_TAGS:
            self._append("\n\n")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._append(f"\n\n{'#' * int(tag[1])} ")
        elif tag == "br":
            self._append("  \n")
        elif tag == "li":
            self._append("\n- ")
        elif tag == "blockquote":
            self._append("\n\n> ")
        elif tag == "pre":
            self.pre_depth += 1
            self._append("\n\n```\n")
        elif tag == "a":
            href = dict(attrs).get("href")
            resolved = urljoin(self.base_url, href) if href else None
            self.links.append(resolved)
            if resolved:
                self._append("[")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.ignore_depth:
            self.ignore_depth -= 1
            return
        if self.title_depth:
            self.title_depth -= 1
            return
        if tag == "a":
            href = self.links.pop() if self.links else None
            if href:
                self._append(f"]({href})")
        elif tag == "pre":
            self._append("\n```\n")
            self.pre_depth = max(0, self.pre_depth - 1)
        elif tag in _BLOCK_TAGS or tag in ("blockquote", "li"):
            self._append("\n")
        if tag in ("article", "main"):
            self.focus_depth = max(0, self.focus_depth - 1)

    def handle_data(self, data: str) -> None:
        if self.ignore_depth:
            return
        if self.title_depth:
            self.title.append(data)
            return
        if self.pre_depth:
            self._append(data)
            return
        text = re.sub(r"\s+", " ", data)
        if text.strip():
            self._append(text)


def _clean_markdown(markdown: str) -> str:
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    markdown = re.sub(r"\n[ \t]+", "\n", markdown)
    markdown = re.sub(r"[ ]+([,.;:!?，。；：！？])", r"\1", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def html_to_markdown(html_text: str, *, base_url: str) -> str:
    """Extract readable Markdown, preferring an article/main region when present."""
    parser = _MarkdownParser(base_url)
    parser.feed(html_text)
    focused = _clean_markdown("".join(parser.focused))
    body = focused if len(focused) >= 40 else _clean_markdown("".join(parser.full))
    title = " ".join("".join(parser.title).split())
    if title and not body.lstrip().startswith("#"):
        body = f"# {title}\n\n{body}" if body else f"# {title}"
    return body
