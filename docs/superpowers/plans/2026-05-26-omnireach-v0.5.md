# omnireach v0.5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]` checkboxes. Refer to spec `docs/superpowers/specs/2026-05-26-omnireach-v0.5-design.md` for code examples and rationale; this plan is the execution-side complement.

**Goal:** Rewrite 4 wrapper adapters to call upstream binaries directly, add Exa booster, downgrade `web` to booster tier, defer wechat/bilibili to v0.6, repair setup/doctor, ship v0.5.0-alpha.

**Architecture:** Each adapter becomes a thin shell-out (or direct API) layer. `Agent-Reach` becomes optional (one-shot `setup --batch` only). Tests use mocked `asyncio.create_subprocess_exec` / `httpx`. Existing trust + ranking + preferences from v0.4 stay intact.

**Tech Stack:** Python 3.11+, pydantic v2, httpx, click, feedparser (NEW core dep), asyncio. Upstream binaries: yt-dlp, gh, rdt-cli (installed by user via `omnireach setup`).

---

## File Structure (created/modified by this plan)

**Created**:
- `omnireach/adapters/exa.py`
- `tests/adapters/test_exa.py`
- `tests/adapters/test_youtube.py` (rewritten coverage)
- `tests/adapters/test_github.py` (new — wasn't covered before)
- `tests/adapters/test_reddit.py` (new)
- `tests/adapters/test_rss.py` (new)
- `scripts/smoke_v0.5.sh` (post-install smoke)

**Rewritten** (delete old body, replace with binary-direct impl):
- `omnireach/adapters/youtube.py`
- `omnireach/adapters/github.py`
- `omnireach/adapters/reddit.py`
- `omnireach/adapters/rss.py`
- `omnireach/commands/setup.py`
- `omnireach/doctor.py`

**Modified**:
- `omnireach/sources.yml` — web tier→booster, add exa, wechat/bilibili tier→wip, dep cleanup
- `omnireach/registry.py` — accept `wip` tier in docstring; no schema change needed
- `omnireach/commands/sources.py` — render 🚧 wip section
- `omnireach/router.py` — rss only routes when query looks like a URL
- `omnireach/cli.py` — booster augment adds `exa` to `_BOOSTER_KEY_ENV`
- `omnireach/installer.py` — strip `pipx install agent-reach` paths (keep file as shim)
- `README.md` — honest deployment chapter
- `pyproject.toml` — add `feedparser>=6.0` to dependencies; bump version 0.5.0-alpha
- `omnireach/__init__.py` — version bump

**Tests modified**:
- `tests/test_registry.py` — wip tier count bump (16 sources total)
- `tests/test_router.py` — URL-only rss routing
- `tests/test_cmd_setup.py` — new per-source setup paths
- `tests/test_doctor.py` — binary detection
- `tests/test_cmd_sources.py` — 🚧 wip section
- `tests/test_cli.py` — exa in booster augment

---

## Task 0: Branch off main

- [ ] **Step 1: Verify clean main**

```bash
cd ~/Projects/omnireach
git status   # clean except uv.lock untracked
git log --oneline -3   # 0bf89f5 v0.5 spec on top
```

- [ ] **Step 2: Branch**

```bash
git checkout -b feat/v0.5-adapter-rewrite
```

---

## Task 1: youtube adapter — direct yt-dlp

**Files:**
- Rewrite: `omnireach/adapters/youtube.py`
- Create: `tests/adapters/test_youtube.py`

- [ ] **Step 1: Failing tests**

Create `tests/adapters/test_youtube.py`:

```python
import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.youtube import YouTubeAdapter


def _mock_proc(stdout: bytes, stderr: bytes = b"", returncode: int = 0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    return proc


def test_is_ready_false_without_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    assert asyncio.run(YouTubeAdapter().is_ready()) is False


def test_is_ready_true_with_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/yt-dlp")
    assert asyncio.run(YouTubeAdapter().is_ready()) is True


def test_search_parses_jsonl(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/yt-dlp")
    payload = "\n".join([
        json.dumps({"title": "Vid 1", "url": "https://youtu.be/a", "uploader": "alice", "timestamp": 1716000000, "view_count": 100}),
        json.dumps({"title": "Vid 2", "webpage_url": "https://youtu.be/b", "uploader": "bob", "view_count": 50}),
    ]).encode()
    with patch("omnireach.adapters.youtube.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_mock_proc(payload))):
        out = asyncio.run(YouTubeAdapter().search("claude", limit=5))
    assert len(out) == 2
    assert out[0].source == "youtube"
    assert out[0].title == "Vid 1"
    assert out[0].url == "https://youtu.be/a"
    assert out[0].author == "alice"
    assert out[0].engagement.views == 100
    assert out[1].url == "https://youtu.be/b"


def test_search_raises_when_binary_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(YouTubeAdapter().search("q"))


def test_search_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/yt-dlp")
    with patch("omnireach.adapters.youtube.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_mock_proc(b"", b"boom", 1))):
        with pytest.raises(AdapterUnavailable):
            asyncio.run(YouTubeAdapter().search("q"))


def test_search_skips_blank_lines(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/yt-dlp")
    payload = b'\n{"title":"x","url":"https://y/x"}\n\n'
    with patch("omnireach.adapters.youtube.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_mock_proc(payload))):
        out = asyncio.run(YouTubeAdapter().search("q"))
    assert len(out) == 1
```

- [ ] **Step 2: Confirm fail**: `uv run pytest tests/adapters/test_youtube.py -v`

- [ ] **Step 3: Rewrite `omnireach/adapters/youtube.py`**

```python
"""YouTube adapter — shells out to yt-dlp."""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timezone

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


def _unix_to_iso(ts: int | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class YouTubeAdapter(AdapterBase):
    name = "youtube"
    requires = ["yt-dlp"]

    async def is_ready(self) -> bool:
        return shutil.which("yt-dlp") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("yt-dlp"):
            raise AdapterUnavailable(
                "youtube", "yt-dlp not installed", hint="omnireach setup youtube"
            )
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            f"ytsearch{limit}:{query}",
            "--flat-playlist",
            "--dump-json",
            "--no-warnings",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("youtube", stderr.decode().strip() or "yt-dlp failed")
        results: list[SearchResult] = []
        for line in stdout.decode().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            results.append(
                SearchResult(
                    source="youtube",
                    adapter="yt-dlp",
                    title=entry.get("title") or "",
                    url=entry.get("url") or entry.get("webpage_url") or "",
                    content="",
                    author=entry.get("uploader"),
                    ts=_unix_to_iso(entry.get("timestamp")),
                    engagement=Engagement(views=entry.get("view_count")),
                    raw=entry,
                )
            )
        return results
```

- [ ] **Step 4: Run tests** — `uv run pytest tests/adapters/test_youtube.py -v && uv run pytest -x`

- [ ] **Step 5: Commit**

```bash
git add omnireach/adapters/youtube.py tests/adapters/test_youtube.py
git commit -m "feat(v0.5): rewrite youtube adapter to call yt-dlp directly"
```

---

## Task 2: github adapter — direct gh CLI

**Files:**
- Rewrite: `omnireach/adapters/github.py`
- Create: `tests/adapters/test_github.py`

- [ ] **Step 1: Failing tests**

Create `tests/adapters/test_github.py`:

```python
import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.github import GitHubAdapter


def _mock_proc(stdout: bytes, returncode: int = 0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, b""))
    proc.returncode = returncode
    return proc


def test_is_ready_false_without_gh(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    assert asyncio.run(GitHubAdapter().is_ready()) is False


def test_is_ready_true_with_gh(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/gh")
    assert asyncio.run(GitHubAdapter().is_ready()) is True


def test_search_combines_repos_and_issues(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/gh")
    repos = json.dumps([
        {"fullName": "ant/repo", "url": "https://github.com/ant/repo",
         "description": "desc", "stargazersCount": 100, "updatedAt": "2026-05-20T00:00:00Z"}
    ]).encode()
    issues = json.dumps([
        {"title": "issue 1", "url": "https://github.com/x/y/issues/1",
         "body": "body", "author": {"login": "alice"}, "createdAt": "2026-05-21T00:00:00Z"}
    ]).encode()
    calls = []

    async def fake_exec(*args, **kw):
        calls.append(args)
        if "repos" in args:
            return _mock_proc(repos)
        return _mock_proc(issues)

    with patch("omnireach.adapters.github.asyncio.create_subprocess_exec", side_effect=fake_exec):
        out = asyncio.run(GitHubAdapter().search("query", limit=4))
    assert any(r.source == "github" and "repo" in r.url for r in out)
    assert any(r.source == "github" and "issues" in r.url for r in out)


def test_search_raises_when_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(GitHubAdapter().search("q"))


def test_search_empty_output(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/gh")
    with patch("omnireach.adapters.github.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_mock_proc(b"[]"))):
        out = asyncio.run(GitHubAdapter().search("q"))
    assert out == []
```

- [ ] **Step 2: Confirm fail**: `uv run pytest tests/adapters/test_github.py -v`

- [ ] **Step 3: Rewrite `omnireach/adapters/github.py`**

```python
"""GitHub adapter — shells out to `gh search`."""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult


class GitHubAdapter(AdapterBase):
    name = "github"
    requires = ["gh"]

    async def is_ready(self) -> bool:
        return shutil.which("gh") is not None

    async def _run(self, *args: str) -> list[dict]:
        proc = await asyncio.create_subprocess_exec(
            "gh", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("github", stderr.decode().strip() or "gh failed")
        try:
            return json.loads(stdout.decode() or "[]")
        except json.JSONDecodeError:
            return []

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("gh"):
            raise AdapterUnavailable("github", "gh CLI not installed",
                                     hint="omnireach setup github")
        half = max(1, limit // 2)
        repo_fields = "fullName,url,description,stargazersCount,updatedAt"
        issue_fields = "title,url,body,author,createdAt"
        repos, issues = await asyncio.gather(
            self._run("search", "repos", query, "--json", repo_fields, "--limit", str(half)),
            self._run("search", "issues", query, "--json", issue_fields, "--limit", str(half)),
            return_exceptions=True,
        )
        results: list[SearchResult] = []
        if isinstance(repos, list):
            for r in repos:
                results.append(SearchResult(
                    source="github", adapter="gh",
                    title=r.get("fullName") or "",
                    url=r.get("url") or "",
                    content=r.get("description") or "",
                    ts=r.get("updatedAt"),
                    raw=r,
                ))
        if isinstance(issues, list):
            for i in issues:
                results.append(SearchResult(
                    source="github", adapter="gh",
                    title=i.get("title") or "",
                    url=i.get("url") or "",
                    content=(i.get("body") or "")[:500],
                    author=(i.get("author") or {}).get("login"),
                    ts=i.get("createdAt"),
                    raw=i,
                ))
        return results
```

- [ ] **Step 4: Tests** — `uv run pytest tests/adapters/test_github.py -v && uv run pytest -x`

- [ ] **Step 5: Commit**

```bash
git add omnireach/adapters/github.py tests/adapters/test_github.py
git commit -m "feat(v0.5): rewrite github adapter to call gh CLI directly"
```

---

## Task 3: reddit adapter — direct rdt-cli

**Files:**
- Rewrite: `omnireach/adapters/reddit.py`
- Create: `tests/adapters/test_reddit.py`

- [ ] **Step 1: Failing tests**

Create `tests/adapters/test_reddit.py`:

```python
import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.reddit import RedditAdapter


def _mock_proc(stdout: bytes, stderr: bytes = b"", returncode: int = 0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    return proc


def test_is_ready_false_without_rdt(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    assert asyncio.run(RedditAdapter().is_ready()) is False


def test_is_ready_true_with_rdt(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/rdt-cli")
    assert asyncio.run(RedditAdapter().is_ready()) is True


def test_search_parses_results(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/rdt-cli")
    payload = json.dumps({
        "results": [
            {
                "title": "Post 1",
                "permalink": "/r/python/comments/abc/post_1",
                "selftext": "body",
                "author": "alice",
                "created_utc": 1716000000,
                "score": 42,
                "num_comments": 7,
                "subreddit": "python",
            },
        ]
    }).encode()
    with patch("omnireach.adapters.reddit.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_mock_proc(payload))):
        out = asyncio.run(RedditAdapter().search("python", limit=5))
    assert len(out) == 1
    assert out[0].source == "reddit"
    assert out[0].title == "Post 1"
    assert "reddit.com/r/python/comments/abc" in out[0].url
    assert out[0].author == "alice"
    assert out[0].engagement.likes == 42
    assert out[0].engagement.comments == 7


def test_search_raises_when_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(RedditAdapter().search("q"))


def test_search_detects_unauth_error(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/rdt-cli")
    with patch("omnireach.adapters.reddit.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_mock_proc(b"", b"not logged in: run `rdt login`", 1))):
        with pytest.raises(AdapterUnavailable) as exc:
            asyncio.run(RedditAdapter().search("q"))
        assert "login" in str(exc.value).lower() or "rdt" in str(exc.value).lower()
```

- [ ] **Step 2: Confirm fail**: `uv run pytest tests/adapters/test_reddit.py -v`

- [ ] **Step 3: Rewrite `omnireach/adapters/reddit.py`**

```python
"""Reddit adapter — shells out to rdt-cli (https://github.com/public-clis/rdt-cli)."""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timezone

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


def _unix_to_iso(ts: float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class RedditAdapter(AdapterBase):
    name = "reddit"
    requires = ["rdt-cli"]

    async def is_ready(self) -> bool:
        return shutil.which("rdt-cli") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("rdt-cli"):
            raise AdapterUnavailable(
                "reddit", "rdt-cli not installed", hint="omnireach setup reddit"
            )
        proc = await asyncio.create_subprocess_exec(
            "rdt-cli", "search", query, "--json", "--limit", str(limit),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode().strip()
            if "login" in err.lower():
                raise AdapterUnavailable(
                    "reddit", "未登录, 运行 `rdt login` 完成 OAuth", hint="rdt login"
                )
            raise AdapterUnavailable("reddit", err or "rdt-cli failed")
        try:
            data = json.loads(stdout.decode() or "{}")
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("reddit", f"non-JSON from rdt-cli: {e}")
        results: list[SearchResult] = []
        for hit in data.get("results", [])[:limit]:
            permalink = hit.get("permalink") or ""
            url = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else permalink
            results.append(SearchResult(
                source="reddit",
                adapter="rdt-cli",
                title=hit.get("title") or "",
                url=url,
                content=hit.get("selftext") or "",
                author=hit.get("author"),
                ts=_unix_to_iso(hit.get("created_utc")),
                engagement=Engagement(
                    likes=hit.get("score"),
                    comments=hit.get("num_comments"),
                ),
                raw=hit,
            ))
        return results
```

- [ ] **Step 4: Tests** — `uv run pytest tests/adapters/test_reddit.py -v && uv run pytest -x`

- [ ] **Step 5: Commit**

```bash
git add omnireach/adapters/reddit.py tests/adapters/test_reddit.py
git commit -m "feat(v0.5): rewrite reddit adapter to call rdt-cli directly"
```

---

## Task 4: rss adapter — feedparser

**Files:**
- Rewrite: `omnireach/adapters/rss.py`
- Create: `tests/adapters/test_rss.py`
- Modify: `pyproject.toml` (add feedparser)

- [ ] **Step 1: Add feedparser dep**

In `pyproject.toml`, find `dependencies` and add `"feedparser>=6.0,<7.0"`. Then:

```bash
uv sync
```

- [ ] **Step 2: Failing tests**

Create `tests/adapters/test_rss.py`:

```python
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


def test_search_parses_feed(monkeypatch, tmp_path: Path):
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
```

- [ ] **Step 3: Rewrite `omnireach/adapters/rss.py`**

```python
"""RSS adapter — Python feedparser. Query MUST be a URL."""

from __future__ import annotations

import asyncio
import re
from email.utils import parsedate_to_datetime

import feedparser

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult

URL_RE = re.compile(r"^(https?|file)://", re.IGNORECASE)


def _parse_ts(entry) -> str | None:
    for field in ("published", "updated", "created"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw).isoformat()
            except (TypeError, ValueError):
                continue
    return None


class RssAdapter(AdapterBase):
    name = "rss"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not URL_RE.match(query.strip()):
            raise AdapterUnavailable(
                "rss", "rss source requires a URL as query",
                hint="omnireach 'https://example.com/feed.xml'",
            )
        feed = await asyncio.to_thread(feedparser.parse, query)
        if feed.bozo and not feed.entries:
            raise AdapterUnavailable("rss", f"feed parse failed: {feed.bozo_exception}")
        results: list[SearchResult] = []
        for entry in feed.entries[:limit]:
            results.append(SearchResult(
                source="rss",
                adapter="feedparser",
                title=entry.get("title") or "",
                url=entry.get("link") or "",
                content=(entry.get("summary") or entry.get("description") or "")[:500],
                author=entry.get("author"),
                ts=_parse_ts(entry),
                raw=dict(entry),
            ))
        return results
```

- [ ] **Step 4: Tests** — `uv run pytest tests/adapters/test_rss.py -v && uv run pytest -x`

- [ ] **Step 5: Commit**

```bash
git add omnireach/adapters/rss.py tests/adapters/test_rss.py pyproject.toml uv.lock
git commit -m "feat(v0.5): rewrite rss adapter to use feedparser (URL queries only)"
```

(Include `uv.lock` if uv created/updated it; otherwise omit.)

---

## Task 5: Exa booster adapter

**Files:**
- Create: `omnireach/adapters/exa.py`
- Create: `tests/adapters/test_exa.py`

- [ ] **Step 1: Failing tests**

Create `tests/adapters/test_exa.py`:

```python
import asyncio
from unittest.mock import patch

import httpx
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.exa import ExaAdapter


def _mock_transport(status: int, json_body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body or {})
    return httpx.MockTransport(handler)


def test_is_ready_false_without_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    assert asyncio.run(ExaAdapter().is_ready()) is False


def test_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    assert asyncio.run(ExaAdapter().is_ready()) is True


def test_search_returns_results_with_cost_paid(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    payload = {
        "results": [
            {"title": "Result 1", "url": "https://e/1", "publishedDate": "2026-05-22T10:00:00Z",
             "text": "snippet 1", "author": "alice"},
            {"title": "Result 2", "url": "https://e/2", "text": "snippet 2"},
        ]
    }
    a = ExaAdapter()
    real_client = httpx.AsyncClient(transport=_mock_transport(200, payload))
    with patch("omnireach.adapters.exa.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(a.search("q", limit=5))
    assert len(out) == 2
    assert out[0].source == "exa"
    assert out[0].cost == "paid"
    assert out[0].title == "Result 1"


def test_search_raises_on_401(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "bad")
    a = ExaAdapter()
    real_client = httpx.AsyncClient(transport=_mock_transport(401))
    with patch("omnireach.adapters.exa.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        with pytest.raises(AdapterUnavailable):
            asyncio.run(a.search("q"))


def test_search_raises_without_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(ExaAdapter().search("q"))
```

- [ ] **Step 2: Confirm fail**: `uv run pytest tests/adapters/test_exa.py -v`

- [ ] **Step 3: Create `omnireach/adapters/exa.py`**

```python
"""Exa Search API booster (paid)."""

from __future__ import annotations

import os

import httpx

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult

EXA_URL = "https://api.exa.ai/search"


class ExaAdapter(AdapterBase):
    name = "exa"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bool(os.environ.get("EXA_API_KEY"))

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        key = os.environ.get("EXA_API_KEY")
        if not key:
            raise AdapterUnavailable("exa", "EXA_API_KEY 未设置", hint="omnireach setup exa")
        headers = {"x-api-key": key, "Content-Type": "application/json"}
        body = {"query": query, "numResults": limit, "type": "auto"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(EXA_URL, json=body, headers=headers)
            except httpx.HTTPError as e:
                raise AdapterUnavailable("exa", f"http error: {e}") from e
        if resp.status_code == 401:
            raise AdapterUnavailable("exa", "API Key 无效 (401)")
        if resp.status_code == 429:
            raise AdapterUnavailable("exa", "rate limited (429)")
        if resp.status_code >= 500:
            raise AdapterUnavailable("exa", f"upstream {resp.status_code}")
        data = resp.json()
        results: list[SearchResult] = []
        for hit in data.get("results", [])[:limit]:
            results.append(SearchResult(
                source="exa",
                adapter="exa-api",
                title=hit.get("title") or "",
                url=hit.get("url") or "",
                content=hit.get("text") or "",
                author=hit.get("author"),
                ts=hit.get("publishedDate"),
                cost="paid",
                raw=hit,
            ))
        return results
```

- [ ] **Step 4: Tests** — `uv run pytest tests/adapters/test_exa.py -v && uv run pytest -x`

- [ ] **Step 5: Commit**

```bash
git add omnireach/adapters/exa.py tests/adapters/test_exa.py
git commit -m "feat(v0.5): Exa booster adapter (web search)"
```

---

## Task 6: sources.yml restructure + wip tier rendering

**Files:**
- Modify: `omnireach/sources.yml`
- Modify: `omnireach/commands/sources.py`
- Modify: `omnireach/cli.py`
- Modify: `tests/test_registry.py`
- Modify: `tests/test_cmd_sources.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Restructure sources.yml**

For each existing source, update according to this table:

| id | new tier | default_in_auto | trust | notes |
|---|---|---|---|---|
| hackernews | ready | true | 0.85 | unchanged |
| web | **booster** | true | 0.70 | requires EXA_API_KEY now (renamed conceptually; alias keeps id `web`) |
| youtube | ready | true | 0.60 | requires yt-dlp |
| github | ready | true | 0.90 | requires gh |
| rss | ready | false | 0.75 | URL-only — router gates entry |
| wechat | **wip** | **false** | 0.55 | v0.6 |
| bilibili | **wip** | **false** | 0.55 | v0.6 |
| reddit | one_step | true | 0.70 | requires rdt-cli + rdt login |
| twitter | heavy | true | 0.60 | unchanged |
| xiaohongshu | heavy | true | 0.50 | unchanged |
| tavily | booster | true | 0.85 | unchanged |
| brave | booster | true | 0.80 | unchanged |
| perplexity | booster | true | 0.90 | unchanged |

Add a new booster entry for exa (between perplexity and end):

```yaml
- id: exa
  tier: booster
  adapter: omnireach.adapters.exa.ExaAdapter
  description: Exa Search API (付费, web search)
  query_hints: []
  default_in_auto: true
  trust: 0.85
  deps:
    auto: []
    manual:
      - step: "去 https://exa.ai 注册并复制 API Key"
        verify: "echo $EXA_API_KEY 非空"
```

For the existing `web` entry, change `tier: ready` → `tier: booster`, description → "Exa-backed web search (付费)", and **change its adapter** to point to `omnireach.adapters.exa.ExaAdapter`. Actually — simpler: **delete the `web` entry entirely** and let `exa` be the only entry. The legacy `web` adapter file (`omnireach/adapters/web.py`) becomes dead code; we keep it on disk for v0.6 reconsideration but unreferenced.

For wechat / bilibili: change `tier` to `wip`, set `default_in_auto: false`, update description to include "(v0.6 重写中)".

Strip all `pipx install agent-reach` deps clauses — replace each source's `deps.auto` with empty list or with the new per-binary install hint.

- [ ] **Step 2: Update tests/test_registry.py**

Existing test asserts `len(reg.sources) == 13`. New count: `10 + exa - web = 10`... wait recount:
- ready: hackernews, youtube, github, rss → 4
- one_step: reddit → 1
- heavy: twitter, xiaohongshu → 2
- booster: tavily, brave, perplexity, exa → 4
- wip: wechat, bilibili → 2
- Total: **13**

(Same count: removed `web`, added `exa`.) Update assertion if needed; should already be 13.

Add tests:

```python
def test_registry_includes_wip_tier():
    from omnireach.registry import load_registry
    reg = load_registry()
    wip = {s.id for s in reg.sources if s.tier == "wip"}
    assert wip == {"wechat", "bilibili"}


def test_registry_has_exa_booster():
    from omnireach.registry import load_registry
    reg = load_registry()
    by_id = {s.id: s for s in reg.sources}
    assert by_id["exa"].tier == "booster"
    assert by_id["exa"].trust == 0.85


def test_registry_web_removed():
    from omnireach.registry import load_registry
    reg = load_registry()
    assert "web" not in {s.id for s in reg.sources}
```

- [ ] **Step 3: Render 🚧 wip in sources command**

In `omnireach/commands/sources.py`, extend tier rendering:

```python
TIER_ICON = {
    "ready": "✅", "one_step": "🟡", "heavy": "🔴",
    "booster": "💎", "wip": "🚧",
}
TIER_LABEL = {
    "ready": "ready", "one_step": "一步配置", "heavy": "重配置",
    "booster": "付费增强", "wip": "v0.6 重写中",
}
```

Render wip tier section after heavy, before booster. wip entries display the source id with `(待实现)` suffix.

- [ ] **Step 4: Add exa to booster augment**

In `omnireach/cli.py`, update `_BOOSTER_KEY_ENV`:

```python
_BOOSTER_KEY_ENV = {
    "tavily": "TAVILY_API_KEY",
    "brave": "BRAVE_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "exa": "EXA_API_KEY",
}
```

- [ ] **Step 5: Update tests/test_cmd_sources.py**

Append:

```python
def test_sources_command_shows_wip_section():
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["sources"])
    assert result.exit_code == 0
    assert "🚧" in result.output or "v0.6" in result.output
    assert "wechat" in result.output
    assert "bilibili" in result.output
```

- [ ] **Step 6: Update tests/test_cli.py**

The existing `test_search_includes_active_booster_in_fanout` should still pass. Add:

```python
def test_search_augment_includes_exa(monkeypatch):
    from omnireach.cli import _augment_with_active_boosters
    from omnireach.registry import load_registry

    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    reg = load_registry()
    out = _augment_with_active_boosters(["hackernews"], reg, explicit_sources=None)
    assert "exa" in out
```

- [ ] **Step 7: Run full suite** — `uv run pytest -x`

- [ ] **Step 8: Commit**

```bash
git add omnireach/sources.yml omnireach/commands/sources.py omnireach/cli.py tests/test_registry.py tests/test_cmd_sources.py tests/test_cli.py
git commit -m "feat(v0.5): sources.yml restructure (web→exa booster, wechat/bilibili→wip)"
```

---

## Task 7: router gates RSS by URL-shape query

**Files:**
- Modify: `omnireach/router.py`
- Modify: `tests/test_router.py`

- [ ] **Step 1: Failing test**

Append to `tests/test_router.py`:

```python
def test_router_includes_rss_only_for_url_query():
    from omnireach.registry import load_registry
    from omnireach.router import RouteRequest, Router
    reg = load_registry()
    router = Router(reg)

    auto = router.plan(RouteRequest(query="claude 4.7", explicit_sources=None, mode="auto"))
    assert "rss" not in auto.source_ids

    url_route = router.plan(RouteRequest(query="https://example.com/feed.xml", explicit_sources=None, mode="auto"))
    assert "rss" in url_route.source_ids
```

- [ ] **Step 2: Update router**

In `omnireach/router.py`, locate where auto fanout is assembled. After collecting default_in_auto sources, gate rss:

```python
import re
_URL_RE = re.compile(r"^(https?|file)://", re.IGNORECASE)

# inside router.plan():
if not _URL_RE.match(request.query.strip()):
    source_ids = [s for s in source_ids if s != "rss"]
elif "rss" not in source_ids:
    # If query is URL but rss got filtered out by default_in_auto=false,
    # still include it
    source_ids.append("rss")
```

(Or simpler: never include rss by default; add it iff query is URL. Since `default_in_auto: false` for rss in Task 6, the gate becomes "URL → add rss".)

- [ ] **Step 3: Tests** — `uv run pytest tests/test_router.py -v && uv run pytest -x`

- [ ] **Step 4: Commit**

```bash
git add omnireach/router.py tests/test_router.py
git commit -m "feat(v0.5): router only routes rss when query is a URL"
```

---

## Task 8: setup wizard — per-source install paths

**Files:**
- Rewrite: `omnireach/commands/setup.py`
- Modify: `tests/test_cmd_setup.py`

- [ ] **Step 1: Replace agent-reach-centric dispatch**

Open `omnireach/commands/setup.py`. Keep BOOSTER_GUIDES + `_setup_booster()` from v0.4 — add `exa` to BOOSTER_GUIDES with signup_url `https://exa.ai`, env `EXA_API_KEY`, label `Exa Search API`, note `付费 web 搜索`.

Add NEW per-source setup handlers:

```python
BINARY_GUIDES = {
    "youtube": {
        "binary": "yt-dlp",
        "install": ["pip", "install", "yt-dlp"],
        "label": "yt-dlp",
    },
    "github": {
        "binary": "gh",
        "install": None,  # system package, no auto install
        "label": "GitHub CLI",
        "manual_hint": "macOS: brew install gh ; Linux/Windows: https://cli.github.com",
    },
    "reddit": {
        "binary": "rdt-cli",
        "install": ["uv", "tool", "install", "rdt-cli"],
        "label": "rdt-cli",
        "post_install": "运行 `rdt login` 完成 Reddit OAuth (浏览器扫码)",
    },
    "rss": {
        "binary": None,  # built-in feedparser
        "install": None,
        "label": "RSS (内置 feedparser)",
    },
}


def _setup_binary(source_id: str) -> None:
    import shutil
    import subprocess
    import click

    g = BINARY_GUIDES[source_id]
    binary = g["binary"]
    if binary is None:
        click.echo(f"✅ {g['label']} 已内置, 无需配置.")
        return
    if shutil.which(binary):
        click.echo(f"✅ {binary} 已在 PATH, 可直接使用.")
        if g.get("post_install"):
            click.echo(f"  ⚠️  下一步: {g['post_install']}")
        return
    click.echo(f"{g['label']} 未安装.")
    if g["install"]:
        if not click.confirm(f"运行 `{' '.join(g['install'])}` 安装?", default=True):
            return
        try:
            subprocess.run(g["install"], check=True)
        except subprocess.CalledProcessError as e:
            click.echo(f"❌ 安装失败: {e}", err=True)
            return
        click.echo(f"✅ {binary} 安装完成.")
        if g.get("post_install"):
            click.echo(f"  ⚠️  下一步: {g['post_install']}")
    else:
        click.echo(f"  👤 请手动安装: {g['manual_hint']}")


def _setup_wip(source_id: str) -> None:
    import click
    click.echo(f"⚠️  {source_id} 在 v0.6 重写中, 当前不可用. 详见 spec v0.5 §4.")
```

In the existing dispatch function, route source_ids to the right handler:

```python
if source_id in BOOSTER_GUIDES:
    _setup_booster(source_id)
elif source_id in BINARY_GUIDES:
    _setup_binary(source_id)
elif source_id in ("wechat", "bilibili"):
    _setup_wip(source_id)
elif source_id in ("twitter", "xiaohongshu"):
    # existing OpenCLI path from v0.3 — leave intact
    ...
elif source_id == "hackernews":
    click.echo("✅ HackerNews 零配置, 无需 setup.")
else:
    click.echo(f"unknown source: {source_id}", err=True)
```

Delete any code path that calls `pipx install agent-reach`. The `installer.py` helper that does this can be left in place but should no longer be called from setup.

- [ ] **Step 2: Update tests/test_cmd_setup.py**

The v0.4 `test_setup_tavily_writes_secrets_env` should still pass. Add:

```python
def test_setup_youtube_installs_yt_dlp(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setattr("shutil.which", lambda b: None)
    calls = []
    def fake_run(cmd, **kw):
        calls.append(cmd)
        import subprocess
        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.setattr("subprocess.run", fake_run)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "youtube"], input="y\n")
    assert result.exit_code == 0
    assert any("yt-dlp" in (c if isinstance(c, str) else " ".join(c)) for c in calls)


def test_setup_wechat_is_wip(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "wechat"])
    assert result.exit_code == 0
    assert "v0.6" in result.output or "wip" in result.output.lower()


def test_setup_github_prompts_manual(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setattr("shutil.which", lambda b: None)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "github"])
    assert result.exit_code == 0
    assert "brew install gh" in result.output or "cli.github.com" in result.output
```

- [ ] **Step 3: Tests** — `uv run pytest tests/test_cmd_setup.py -v && uv run pytest -x`

- [ ] **Step 4: Commit**

```bash
git add omnireach/commands/setup.py tests/test_cmd_setup.py
git commit -m "feat(v0.5): setup wizard rewrites — per-source install paths, no more agent-reach"
```

---

## Task 9: doctor — detect real binaries

**Files:**
- Rewrite: `omnireach/doctor.py`
- Modify: `tests/test_doctor.py`

- [ ] **Step 1: Read existing doctor**

```bash
cat omnireach/doctor.py
cat tests/test_doctor.py
```

- [ ] **Step 2: Rewrite doctor**

The new doctor iterates all registered sources and computes status:

```python
"""Doctor — per-source readiness check."""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass

from omnireach.registry import load_registry


@dataclass
class SourceStatus:
    id: str
    tier: str
    ok: bool
    detail: str
    fix_hint: str = ""


BINARY_FOR_SOURCE = {
    "youtube": "yt-dlp",
    "github": "gh",
    "reddit": "rdt-cli",
    "twitter": "openrouter",  # OpenCLI binary; adjust if existing v0.3 used different name
    "xiaohongshu": "openrouter",
}

ENV_FOR_BOOSTER = {
    "tavily": "TAVILY_API_KEY",
    "brave": "BRAVE_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "exa": "EXA_API_KEY",
}


async def run_doctor() -> list[SourceStatus]:
    reg = load_registry()
    statuses: list[SourceStatus] = []
    for spec in reg.sources:
        sid = spec.id
        if spec.tier == "wip":
            statuses.append(SourceStatus(sid, spec.tier, ok=False,
                detail="🚧 v0.6 重写中",
                fix_hint=""))
            continue
        if sid == "hackernews":
            statuses.append(SourceStatus(sid, spec.tier, ok=True, detail="HTTP API (Algolia)"))
            continue
        if sid == "rss":
            statuses.append(SourceStatus(sid, spec.tier, ok=True,
                detail="feedparser (内置), 调用形态: omnireach <URL>"))
            continue
        if sid in BINARY_FOR_SOURCE:
            binary = BINARY_FOR_SOURCE[sid]
            if shutil.which(binary):
                statuses.append(SourceStatus(sid, spec.tier, ok=True, detail=f"{binary} 在 PATH"))
            else:
                statuses.append(SourceStatus(sid, spec.tier, ok=False,
                    detail=f"{binary} 不在 PATH",
                    fix_hint=f"omnireach setup {sid}"))
            continue
        if sid in ENV_FOR_BOOSTER:
            env = ENV_FOR_BOOSTER[sid]
            if os.environ.get(env):
                statuses.append(SourceStatus(sid, spec.tier, ok=True, detail=f"{env} 已配"))
            else:
                statuses.append(SourceStatus(sid, spec.tier, ok=False,
                    detail=f"{env} 未配",
                    fix_hint=f"omnireach setup {sid}"))
            continue
        statuses.append(SourceStatus(sid, spec.tier, ok=False, detail="未知 / 未实现",
                                     fix_hint=""))
    return statuses
```

(If `BINARY_FOR_SOURCE` for twitter/xiaohongshu uses wrong binary name, read existing v0.3 adapter files for the correct name and substitute.)

- [ ] **Step 3: Update tests/test_doctor.py**

Rewrite to use the new SourceStatus dataclass:

```python
import asyncio
import os
from omnireach.doctor import run_doctor


def test_doctor_reports_each_source(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    for env in ("TAVILY_API_KEY", "BRAVE_API_KEY", "PERPLEXITY_API_KEY", "EXA_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    statuses = asyncio.run(run_doctor())
    ids = {s.id for s in statuses}
    assert {"hackernews", "youtube", "github", "reddit", "rss", "exa", "wechat", "bilibili"}.issubset(ids)


def test_doctor_marks_hackernews_ok(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    statuses = asyncio.run(run_doctor())
    hn = next(s for s in statuses if s.id == "hackernews")
    assert hn.ok is True


def test_doctor_marks_wip_not_ok(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    statuses = asyncio.run(run_doctor())
    wechat = next(s for s in statuses if s.id == "wechat")
    assert wechat.ok is False
    assert "v0.6" in wechat.detail or "重写" in wechat.detail


def test_doctor_marks_youtube_ok_with_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/yt-dlp" if b == "yt-dlp" else None)
    statuses = asyncio.run(run_doctor())
    yt = next(s for s in statuses if s.id == "youtube")
    assert yt.ok is True
```

- [ ] **Step 4: Update CLI doctor_cmd in `omnireach/cli.py`** if it depends on the old return shape — the CLI command should iterate `SourceStatus` and print:

```
  source           tier    status
  hackernews       ready   ✅ HTTP API (Algolia)
  youtube          ready   ❌ yt-dlp 不在 PATH  → omnireach setup youtube
  ...
```

Find the existing doctor CLI rendering and adapt.

- [ ] **Step 5: Tests** — `uv run pytest tests/test_doctor.py -v && uv run pytest -x`

- [ ] **Step 6: Commit**

```bash
git add omnireach/doctor.py omnireach/cli.py tests/test_doctor.py
git commit -m "feat(v0.5): doctor detects real upstream binaries; drops agent-reach probes"
```

---

## Task 10: README rewrite + smoke script

**Files:**
- Modify: `README.md`
- Create: `scripts/smoke_v0.5.sh`

- [ ] **Step 1: README — honest deployment chapter**

Replace the existing "支持的源" + "快速开始" sections with a layered honest version:

```markdown
## 快速开始

```bash
uv tool install git+https://github.com/Daily-AC/omnireach.git
omnireach init                  # 写默认 ~/.omnireach/preferences.toml
omnireach search "vibe coding"  # HN 立即可用
```

零配置只跑 HackerNews。要打开其他源:

```bash
omnireach setup youtube   # pip install yt-dlp
omnireach setup github    # brew install gh (macOS)
omnireach setup reddit    # uv tool install rdt-cli + rdt login
omnireach setup exa       # 拿 EXA_API_KEY (付费)
```

## 支持的源

| 源 | tier | 依赖 | 说明 |
|---|---|---|---|
| hackernews | ✅ ready | 无 | 直连 Algolia, 零配置 |
| youtube | ✅ ready (装 yt-dlp 后) | `yt-dlp` | `omnireach setup youtube` |
| github | ✅ ready (装 gh 后) | `gh` CLI | `omnireach setup github`; 需 `gh auth login` |
| rss | ✅ ready | 内置 feedparser | query 必须是 URL |
| reddit | 🟡 one_step | `rdt-cli` + `rdt login` | `omnireach setup reddit` |
| twitter | 🔴 heavy | OpenCLI + Chrome 扩展 | v0.3 文档 |
| xiaohongshu | 🔴 heavy | OpenCLI + Chrome 扩展 | v0.3 文档 |
| 💎 tavily | booster | env `TAVILY_API_KEY` | 付费 |
| 💎 brave | booster | env `BRAVE_API_KEY` | 付费 |
| 💎 perplexity | booster | env `PERPLEXITY_API_KEY` | 付费 |
| 💎 exa | booster | env `EXA_API_KEY` | 付费 web search |
| 🚧 wechat | wip | — | v0.6 重写中 |
| 🚧 bilibili | wip | — | v0.6 重写中 |

注: v0.4 及之前曾把 `web` 列为零配置，实际不可用 (架构 bug)。v0.5 起 web search 走 💎 exa booster。

## 上游依赖

omnireach 不在运行时调用任何 wrapper, 而是直接 shell 出 yt-dlp / gh / rdt-cli。每个 binary 用 `omnireach setup <X>` 引导安装。

如果你想一次性装齐, 可以装 Agent-Reach (上游 installer):

```bash
uv tool install git+https://github.com/Panniantong/Agent-Reach.git
agent-reach install --channels youtube,github,reddit
```

Agent-Reach 完全可选 — omnireach 自己 doctor / search 都不依赖它。
```

Update the v0.4 "💎 付费 booster" section to include exa.

- [ ] **Step 2: Smoke script**

Create `scripts/smoke_v0.5.sh`:

```bash
#!/usr/bin/env bash
# v0.5 smoke: verify a fresh deployment can search HN (the only true zero-config source)
set -euo pipefail

cd "$(dirname "$0")/.."

uv pip install -e . --reinstall >/dev/null
VERSION=$(uv run omnireach --version)
echo "omnireach version: $VERSION"
[[ "$VERSION" == *"0.5.0-alpha"* ]] || { echo "version mismatch"; exit 1; }

echo "--- omnireach sources ---"
uv run omnireach sources

echo "--- omnireach doctor ---"
uv run omnireach doctor

echo "--- search 'vibe coding' (HN only, no setup) ---"
uv run omnireach search "vibe coding" --limit 3 --timeout 30 | head -20
```

Make it executable:

```bash
chmod +x scripts/smoke_v0.5.sh
```

- [ ] **Step 3: Run smoke**

```bash
scripts/smoke_v0.5.sh
# Expected: HN 3 hits, other sources show "not in PATH" but exit 0
```

- [ ] **Step 4: Commit**

```bash
git add README.md scripts/smoke_v0.5.sh
git commit -m "docs(v0.5): rewrite README deployment chapter + add smoke script"
```

---

## Task 11: Version bump + PR + merge + tag

**Files:**
- Modify: `pyproject.toml`
- Modify: `omnireach/__init__.py`

- [ ] **Step 1: Version**

Bump both to `"0.5.0-alpha"`.

- [ ] **Step 2: Final pytest + smoke**

```bash
uv run pytest -x
scripts/smoke_v0.5.sh
```

Both green.

- [ ] **Step 3: Commit + push**

```bash
git add pyproject.toml omnireach/__init__.py
git commit -m "chore(v0.5): bump to 0.5.0-alpha"
git push -u origin feat/v0.5-adapter-rewrite
```

- [ ] **Step 4: PR + merge + tag**

```bash
gh pr create --title "feat: omnireach v0.5 — rewrite adapters to call upstream binaries directly" --body "$(cat <<'EOF'
## Summary
- **Architecture fix**: All wrapper adapters now shell out to actual upstream binaries (yt-dlp / gh / rdt-cli) or import libraries (feedparser) directly. Agent-Reach was misused as a search proxy in v0.1–v0.4; v0.5 demotes it to optional installer.
- **New booster**: Exa Search API (`EXA_API_KEY`).
- **Web search demotion**: `web` source removed; web search now requires a booster Key (Exa/Tavily/Brave/Perplexity). Zero-config web search is not physically possible.
- **wip tier**: wechat / bilibili marked 🚧 wip, deferred to v0.6.
- **Honest README**: deployment chapter rewritten to list real per-source dependencies.

## Test plan
- [x] Adapter unit tests: youtube, github, reddit, rss, exa (all mock-based)
- [x] Router tests: rss only routes when query is a URL
- [x] Doctor tests: binary-detection per source
- [x] Setup tests: per-source install paths, no more `pipx install agent-reach`
- [x] Full pytest suite green
- [x] scripts/smoke_v0.5.sh passes (HN works, others reported missing)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --squash --delete-branch
git checkout main && git pull
git tag v0.5.0-alpha && git push origin v0.5.0-alpha
```

- [ ] **Step 5: Verify**

```bash
git log --oneline -3
git tag -l | tail
```

`v0.5.0-alpha` should be the newest tag.

---

## Self-review notes

- **Spec coverage**: v0.5 spec §2 decisions all addressed in tasks 1-10. §4 architecture matches the per-task adapter rewrites. §5 detailed designs are inlined into tasks 1-5. §6 setup wizard → task 8. §7 doctor → task 9. §8 file list 1:1 matches plan.
- **Placeholder scan**: All code blocks complete with full implementations. No TODO/TBD.
- **Type consistency**: `SourceStatus` dataclass introduced in task 9 must match what the CLI doctor rendering expects in task 9 step 4. `_BOOSTER_KEY_ENV` extended in task 6 step 4; doctor's `ENV_FOR_BOOSTER` in task 9 step 2 are independent dicts but stay in sync via review.
- **Ordering**: tasks 1-5 (adapter rewrites + Exa) are independent of each other; task 6 (sources.yml) depends on tasks 1-5 existing; tasks 7-9 depend on task 6; task 10 (README) wraps; task 11 ships.
- **Risk**: Task 4 (rss) adds `feedparser` to runtime deps — if uv balks at the version pin, drop the pin to just `feedparser`. Task 9 doctor's `BINARY_FOR_SOURCE` for twitter/xiaohongshu may need adjustment based on real v0.3 binary names; the implementer must verify.
