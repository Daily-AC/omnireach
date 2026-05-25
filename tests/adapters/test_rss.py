import asyncio
from pathlib import Path

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.rss import RssAdapter


RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Example</title>
<link>https://example.com</link>
<item>
  <title>Post One</title>
  <link>https://example.com/1</link>
  <description>Body one</description>
  <pubDate>Tue, 20 May 2026 10:00:00 +0000</pubDate>
  <author>alice@example.com</author>
</item>
<item>
  <title>Post Two</title>
  <link>https://example.com/2</link>
  <description>Body two</description>
</item>
</channel></rss>"""


def test_is_ready_always_true():
    assert asyncio.run(RssAdapter().is_ready()) is True


def test_search_rejects_non_url():
    with pytest.raises(AdapterUnavailable):
        asyncio.run(RssAdapter().search("not a url"))


def test_search_parses_feed(tmp_path: Path):
    feed = tmp_path / "feed.xml"
    feed.write_text(RSS_FIXTURE)
    url = f"file://{feed}"
    out = asyncio.run(RssAdapter().search(url, limit=5))
    assert len(out) == 2
    assert out[0].source == "rss"
    assert out[0].title == "Post One"
    assert out[0].url == "https://example.com/1"
    assert out[0].author == "alice@example.com"
    assert out[0].ts is not None
    assert out[1].title == "Post Two"


def test_search_respects_limit(tmp_path: Path):
    feed = tmp_path / "feed.xml"
    feed.write_text(RSS_FIXTURE)
    out = asyncio.run(RssAdapter().search(f"file://{feed}", limit=1))
    assert len(out) == 1
