# omnireach v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship omnireach v0.1 — a Python CLI + Claude Code Skill that gives users a single `omnireach "<query>"` command which fans out to 7 zero-config sources (web / hackernews / youtube / github / rss / 微信公众号 / B站) and returns normalized JSON results. Establishes the umbrella + adapter-shell architecture so v0.2+ can bolt on more sources.

**Architecture:** Umbrella + adapter-shells. Our package contains the contract (`SearchResult`), Source Registry (yaml-driven), Router (heuristic source picking), Dispatcher (asyncio concurrent fanout), Normalizer/Scorer, and a `cli.py` entry. Each adapter is a thin shell: most subprocess-call `agent-reach`; HN talks to public JSON directly. Agent-Reach is auto-installed via `pipx` on first use of an adapter that needs it. The Skill manifest is a one-liner that `exec`s the CLI.

**Tech Stack:** Python 3.10+, Click (CLI), pydantic v2 (contracts), httpx (HN JSON, parallel HTTP), PyYAML (registry), Rich (pretty zh output), pytest + pytest-asyncio + respx (HTTP mocking), pexpect (wizard test replay), pipx (upstream installer).

**Spec reference:** `docs/superpowers/specs/2026-05-25-omnireach-design.md`

---

## File Structure (created by this plan)

```
omnireach/
├── pyproject.toml                           # Task 1
├── README.md                                # Task 21
├── LICENSE                                  # Task 1
├── .gitignore                               # Task 1
├── omnireach/
│   ├── __init__.py                          # Task 1 (with __version__)
│   ├── __main__.py                          # Task 9 (entry for python -m)
│   ├── cli.py                               # Task 9 (Click group + search)
│   ├── contract.py                          # Task 2 (SearchResult, SearchEnvelope)
│   ├── adapters/
│   │   ├── __init__.py                      # Task 3
│   │   ├── base.py                          # Task 3 (AdapterBase ABC)
│   │   ├── hackernews.py                    # Task 4
│   │   ├── web.py                           # Task 12
│   │   ├── youtube.py                       # Task 13
│   │   ├── github.py                        # Task 14
│   │   ├── rss.py                           # Task 15
│   │   ├── wechat.py                        # Task 16
│   │   └── bilibili.py                      # Task 17
│   ├── sources.yml                          # Task 5
│   ├── registry.py                          # Task 5
│   ├── router.py                            # Task 6
│   ├── dispatcher.py                        # Task 7
│   ├── normalizer.py                        # Task 8
│   ├── scorer.py                            # Task 8
│   ├── doctor.py                            # Task 10
│   ├── installer.py                         # Task 11
│   └── commands/
│       ├── __init__.py                      # Task 18
│       ├── init.py                          # Task 18
│       └── sources.py                       # Task 19
├── tests/
│   ├── __init__.py
│   ├── conftest.py                          # Task 1 (pytest config + fixtures dir)
│   ├── test_contract.py                     # Task 2
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── test_base.py                     # Task 3
│   │   ├── test_hackernews.py               # Task 4
│   │   ├── test_web.py                      # Task 12
│   │   ├── test_youtube.py                  # Task 13
│   │   ├── test_github.py                   # Task 14
│   │   ├── test_rss.py                      # Task 15
│   │   ├── test_wechat.py                   # Task 16
│   │   └── test_bilibili.py                 # Task 17
│   ├── test_registry.py                     # Task 5
│   ├── test_router.py                       # Task 6
│   ├── test_dispatcher.py                   # Task 7
│   ├── test_normalizer_scorer.py            # Task 8
│   ├── test_cli.py                          # Task 9
│   ├── test_doctor.py                       # Task 10
│   ├── test_installer.py                    # Task 11
│   └── fixtures/
│       └── hn_topstories.json               # Task 4
├── .claude-plugin/
│   ├── plugin.json                          # Task 20
│   └── skills/
│       └── omnireach/
│           └── SKILL.md                     # Task 20
└── docs/
    └── superpowers/
        ├── specs/2026-05-25-omnireach-design.md  (already exists)
        └── plans/2026-05-25-omnireach-v0.1.md    (this file)
```

---

## Task 1: Project bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `LICENSE`
- Create: `.gitignore`
- Create: `omnireach/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "omnireach"
version = "0.1.0"
description = "全网通搜索: web + 多平台 (Twitter / Reddit / YouTube / B站 / 小红书 / HN / GitHub) — 一个 CLI + Skill 解决中转站 Agent 用不了 WebSearch 的问题"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "Daily-AC", email = "zoned-group@alum.calarts.edu" }]
keywords = ["claude", "search", "agent", "skill", "cli"]
classifiers = [
  "Development Status :: 3 - Alpha",
  "License :: OSI Approved :: MIT License",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
]
dependencies = [
  "click>=8.1",
  "pydantic>=2.5",
  "httpx>=0.27",
  "PyYAML>=6.0",
  "rich>=13.7",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "respx>=0.21",
  "pexpect>=4.9",
]

[project.scripts]
omnireach = "omnireach.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["omnireach"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create `LICENSE` (MIT)**

```
MIT License

Copyright (c) 2026 Daily-AC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Create `.gitignore`**

```
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
dist/
build/
.pytest_cache/
.coverage
.DS_Store
*.swp
.claude/
.env
```

- [ ] **Step 4: Create `omnireach/__init__.py`**

```python
"""omnireach: 全网通 — web + multi-platform search for proxy-station agent users."""

__version__ = "0.1.0"
```

- [ ] **Step 5: Create `tests/__init__.py` (empty) and `tests/conftest.py`**

```python
# tests/conftest.py
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
```

- [ ] **Step 6: Install in editable mode and verify**

```bash
cd ~/Projects/omnireach && pip install -e ".[dev]"
```

Expected: install succeeds, `omnireach --help` does not yet work (entry exists but module empty — that's fine).

```bash
cd ~/Projects/omnireach && python -c "import omnireach; print(omnireach.__version__)"
```

Expected: `0.1.0`

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/omnireach && git add . && git commit -m "chore: bootstrap omnireach python package"
```

---

## Task 2: SearchResult contract

**Files:**
- Create: `omnireach/contract.py`
- Create: `tests/test_contract.py`

- [ ] **Step 1: Write failing test**

`tests/test_contract.py`:

```python
import json

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
        SearchResult.model_validate({"source": 123, "title": "x", "url": "x"})


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
```

- [ ] **Step 2: Run test, expect ImportError**

```bash
cd ~/Projects/omnireach && pytest tests/test_contract.py -x
```

Expected: FAIL with `ModuleNotFoundError: No module named 'omnireach.contract'`

- [ ] **Step 3: Implement `omnireach/contract.py`**

```python
"""SearchResult JSON contract — the boundary between omnireach core and adapters."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Engagement(BaseModel):
    model_config = ConfigDict(extra="allow")
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    views: int | None = None


class SearchResult(BaseModel):
    """One normalized hit from one source."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="logical source id, e.g. 'hackernews'")
    adapter: str = Field(description="which adapter produced this, e.g. 'agent-reach'")
    title: str
    url: str
    content: str = ""
    author: str | None = None
    ts: str | None = Field(default=None, description="ISO 8601 publish ts")
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    engagement: Engagement | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class SourceError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    error: str


class SearchEnvelope(BaseModel):
    """The top-level JSON returned by `omnireach "<query>"`."""

    model_config = ConfigDict(extra="forbid")

    query: str
    ts: str
    results: list[SearchResult] = Field(default_factory=list)
    errors: list[SourceError] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/test_contract.py -x
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/contract.py tests/test_contract.py && git commit -m "feat(contract): SearchEnvelope + SearchResult pydantic models"
```

---

## Task 3: AdapterBase ABC

**Files:**
- Create: `omnireach/adapters/__init__.py` (empty)
- Create: `omnireach/adapters/base.py`
- Create: `tests/adapters/__init__.py` (empty)
- Create: `tests/adapters/test_base.py`

- [ ] **Step 1: Write failing test**

`tests/adapters/test_base.py`:

```python
import pytest

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult


class DummyAdapter(AdapterBase):
    name = "dummy"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        return [
            SearchResult(
                source="dummy",
                adapter="dummy",
                title=f"hit for {query}",
                url="https://e.x/1",
                content="x",
                ts="2026-05-25T12:00:00Z",
                score=0.5,
            )
        ]


async def test_dummy_adapter_search():
    a = DummyAdapter()
    out = await a.search("hello")
    assert len(out) == 1
    assert out[0].title == "hit for hello"


async def test_base_cannot_instantiate():
    with pytest.raises(TypeError):
        AdapterBase()  # type: ignore[abstract]


def test_adapter_unavailable_carries_hint():
    exc = AdapterUnavailable("dummy", "agent-reach not installed", hint="pipx install agent-reach")
    assert "agent-reach" in str(exc)
    assert exc.hint == "pipx install agent-reach"
```

- [ ] **Step 2: Run, expect FAIL (module missing)**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_base.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/adapters/__init__.py` (empty file)**

```python
```

- [ ] **Step 4: Implement `omnireach/adapters/base.py`**

```python
"""AdapterBase — every source adapter inherits this."""

from __future__ import annotations

from abc import ABC, abstractmethod

from omnireach.contract import SearchResult


class AdapterUnavailable(Exception):
    """Raised when an adapter's upstream binary / auth is missing."""

    def __init__(self, source: str, reason: str, *, hint: str | None = None) -> None:
        super().__init__(f"adapter {source} unavailable: {reason}")
        self.source = source
        self.reason = reason
        self.hint = hint


class AdapterBase(ABC):
    """Contract every adapter must satisfy.

    Adapters are responsible for: (1) checking whether their upstream is
    reachable (`is_ready`) and (2) translating an upstream call's output
    into a list of normalized SearchResult.
    """

    name: str = ""           # override in subclass; matches sources.yml id
    requires: list[str] = []  # CLI binaries / pip pkgs the adapter needs

    @abstractmethod
    async def is_ready(self) -> bool:
        """Cheap probe: returns True if .search() is likely to succeed."""

    @abstractmethod
    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        """Run a search. Must raise AdapterUnavailable rather than returning [] on auth/missing-bin."""
```

- [ ] **Step 5: Run tests, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_base.py -x
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/adapters/ tests/adapters/ && git commit -m "feat(adapters): AdapterBase ABC + AdapterUnavailable"
```

---

## Task 4: HackerNews adapter (reference, no upstream dep)

**Files:**
- Create: `tests/fixtures/hn_topstories.json`
- Create: `tests/fixtures/hn_item_1.json`
- Create: `omnireach/adapters/hackernews.py`
- Create: `tests/adapters/test_hackernews.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/hn_topstories.json`:

```json
[1, 2]
```

`tests/fixtures/hn_item_1.json`:

```json
{
  "id": 1,
  "title": "Claude 4.7 prompt caching benchmarks",
  "url": "https://example.com/post-1",
  "by": "alice",
  "time": 1748160000,
  "score": 250,
  "descendants": 88,
  "type": "story"
}
```

`tests/fixtures/hn_item_2.json`:

```json
{
  "id": 2,
  "title": "Show HN: omnireach — search the whole internet from your agent",
  "url": "https://example.com/post-2",
  "by": "bob",
  "time": 1748170000,
  "score": 42,
  "descendants": 6,
  "type": "story"
}
```

- [ ] **Step 2: Write failing test**

`tests/adapters/test_hackernews.py`:

```python
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
```

- [ ] **Step 3: Run, expect FAIL (module missing)**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_hackernews.py -x
```

Expected: ImportError.

- [ ] **Step 4: Implement `omnireach/adapters/hackernews.py`**

```python
"""HackerNews adapter — talks directly to public JSON API, no upstream needed."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from omnireach.adapters.base import AdapterBase
from omnireach.contract import Engagement, SearchResult

HN_BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsAdapter(AdapterBase):
    name = "hackernews"
    requires: list[str] = []  # zero-config

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        q = query.lower()
        async with httpx.AsyncClient(timeout=15.0) as client:
            top = (await client.get(f"{HN_BASE}/topstories.json")).json()
            top_ids = top[:200]  # widen pool, filter client-side

            async def fetch(item_id: int) -> dict | None:
                try:
                    return (await client.get(f"{HN_BASE}/item/{item_id}.json")).json()
                except Exception:
                    return None

            items = await asyncio.gather(*[fetch(i) for i in top_ids])

        matches: list[SearchResult] = []
        for it in items:
            if not it or it.get("type") != "story":
                continue
            title = it.get("title") or ""
            if q not in title.lower():
                continue
            ts = datetime.fromtimestamp(it.get("time", 0), tz=timezone.utc).isoformat()
            matches.append(
                SearchResult(
                    source="hackernews",
                    adapter="builtin",
                    title=title,
                    url=it.get("url") or f"https://news.ycombinator.com/item?id={it['id']}",
                    content="",
                    author=it.get("by"),
                    ts=ts,
                    score=min(1.0, (it.get("score") or 0) / 500.0),
                    engagement=Engagement(
                        likes=it.get("score"),
                        comments=it.get("descendants"),
                    ),
                    raw=it,
                )
            )
            if len(matches) >= limit:
                break
        return matches
```

- [ ] **Step 5: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_hackernews.py -x
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/adapters/hackernews.py tests/adapters/test_hackernews.py tests/fixtures/ && git commit -m "feat(adapters): hackernews adapter via public JSON API"
```

---

## Task 5: Source Registry (sources.yml + loader)

**Files:**
- Create: `omnireach/sources.yml`
- Create: `omnireach/registry.py`
- Create: `tests/test_registry.py`

- [ ] **Step 1: Create `omnireach/sources.yml`**

```yaml
# Source Registry — single source of truth for available sources.
# Schema:
#   id: string                         (matches AdapterBase.name)
#   tier: ready | one_step | heavy     (visualized in `omnireach sources`)
#   adapter: python.dotted.path        (importable AdapterBase subclass)
#   description: human label (zh)
#   query_hints: [str]                 (router weights these queries toward this source)
#   default_in_auto: bool              (included in auto fanout when ready)
#   deps:
#     auto: [{kind: pipx|npm|pip, name: str}]
#     manual: [{step: str, verify: str}]

- id: hackernews
  tier: ready
  adapter: omnireach.adapters.hackernews.HackerNewsAdapter
  description: HackerNews 全文搜索
  query_hints: [hn, hackernews, "show hn"]
  default_in_auto: true
  deps: { auto: [], manual: [] }

- id: web
  tier: ready
  adapter: omnireach.adapters.web.WebSearchAdapter
  description: 全网搜索 (Jina Reader + MCP, 免费)
  query_hints: []
  default_in_auto: true
  deps:
    auto:
      - { kind: pipx, name: agent-reach }
    manual: []

- id: youtube
  tier: ready
  adapter: omnireach.adapters.youtube.YouTubeAdapter
  description: YouTube 视频搜索 + 字幕提取
  query_hints: [youtube, "video", "视频", "教程"]
  default_in_auto: true
  deps:
    auto:
      - { kind: pipx, name: agent-reach }
    manual: []

- id: github
  tier: ready
  adapter: omnireach.adapters.github.GitHubAdapter
  description: GitHub 仓库/Issue/Discussion 搜索
  query_hints: [github, repo, issue, "源码"]
  default_in_auto: true
  deps:
    auto:
      - { kind: pipx, name: agent-reach }
    manual: []

- id: rss
  tier: ready
  adapter: omnireach.adapters.rss.RSSAdapter
  description: RSS / Atom 源阅读
  query_hints: [rss, atom, feed, "订阅"]
  default_in_auto: false
  deps:
    auto:
      - { kind: pipx, name: agent-reach }
    manual: []

- id: wechat
  tier: ready
  adapter: omnireach.adapters.wechat.WeChatAdapter
  description: 微信公众号文章搜索 (全文 Markdown)
  query_hints: ["微信", "公众号", wechat]
  default_in_auto: true
  deps:
    auto:
      - { kind: pipx, name: agent-reach }
    manual: []

- id: bilibili
  tier: ready
  adapter: omnireach.adapters.bilibili.BilibiliAdapter
  description: B站视频搜索 + 字幕 (海外/服务器需配代理)
  query_hints: ["bilibili", "b站", "哔哩"]
  default_in_auto: true
  deps:
    auto:
      - { kind: pipx, name: agent-reach }
    manual: []
```

- [ ] **Step 2: Write failing test**

`tests/test_registry.py`:

```python
import pytest

from omnireach.registry import Registry, SourceSpec, load_registry


def test_load_registry_returns_all_sources():
    reg = load_registry()
    ids = [s.id for s in reg.sources]
    assert "hackernews" in ids
    assert "web" in ids
    assert "wechat" in ids
    assert "bilibili" in ids
    assert len(reg.sources) >= 7


def test_get_by_id():
    reg = load_registry()
    hn = reg.get("hackernews")
    assert hn.tier == "ready"
    assert hn.adapter.endswith("HackerNewsAdapter")


def test_default_in_auto_filters():
    reg = load_registry()
    auto = [s.id for s in reg.default_auto_sources()]
    assert "hackernews" in auto
    assert "rss" not in auto


def test_get_unknown_raises():
    reg = load_registry()
    with pytest.raises(KeyError):
        reg.get("does-not-exist")


def test_source_with_hint_matches_query():
    reg = load_registry()
    hits = reg.sources_matching_hints("YouTube 教程")
    ids = [s.id for s in hits]
    assert "youtube" in ids
```

- [ ] **Step 3: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/test_registry.py -x
```

Expected: ImportError.

- [ ] **Step 4: Implement `omnireach/registry.py`**

```python
"""Source Registry — loads sources.yml, exposes typed access."""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REGISTRY_PATH = Path(__file__).parent / "sources.yml"


@dataclass
class Dep:
    kind: str
    name: str = ""
    step: str = ""
    verify: str = ""


@dataclass
class SourceSpec:
    id: str
    tier: str  # ready | one_step | heavy
    adapter: str  # dotted import path
    description: str
    query_hints: list[str] = field(default_factory=list)
    default_in_auto: bool = False
    deps_auto: list[Dep] = field(default_factory=list)
    deps_manual: list[Dep] = field(default_factory=list)

    def load_adapter_class(self):
        module_path, _, cls_name = self.adapter.rpartition(".")
        mod = importlib.import_module(module_path)
        return getattr(mod, cls_name)


@dataclass
class Registry:
    sources: list[SourceSpec]

    def get(self, source_id: str) -> SourceSpec:
        for s in self.sources:
            if s.id == source_id:
                return s
        raise KeyError(source_id)

    def default_auto_sources(self) -> list[SourceSpec]:
        return [s for s in self.sources if s.default_in_auto]

    def sources_matching_hints(self, query: str) -> list[SourceSpec]:
        q = query.lower()
        out: list[SourceSpec] = []
        for s in self.sources:
            if any(h.lower() in q for h in s.query_hints):
                out.append(s)
        return out


def load_registry(path: Path | None = None) -> Registry:
    path = path or REGISTRY_PATH
    raw = yaml.safe_load(path.read_text())
    sources: list[SourceSpec] = []
    for entry in raw:
        deps = entry.get("deps") or {}
        spec = SourceSpec(
            id=entry["id"],
            tier=entry["tier"],
            adapter=entry["adapter"],
            description=entry["description"],
            query_hints=entry.get("query_hints", []),
            default_in_auto=entry.get("default_in_auto", False),
            deps_auto=[Dep(**d) for d in (deps.get("auto") or [])],
            deps_manual=[Dep(**d) for d in (deps.get("manual") or [])],
        )
        sources.append(spec)
    return Registry(sources=sources)
```

- [ ] **Step 5: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/test_registry.py -x
```

Expected: 5 passed. (Some adapters don't exist yet — that's OK, `load_adapter_class` isn't called by these tests.)

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/sources.yml omnireach/registry.py tests/test_registry.py && git commit -m "feat(registry): sources.yml + typed loader"
```

---

## Task 6: Router

**Files:**
- Create: `omnireach/router.py`
- Create: `tests/test_router.py`

- [ ] **Step 1: Write failing test**

`tests/test_router.py`:

```python
from omnireach.registry import load_registry
from omnireach.router import Route, RouteRequest, Router


def test_explicit_on_overrides_auto():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="anything", explicit_sources=["hackernews"]))
    assert route.source_ids == ["hackernews"]


def test_auto_uses_hints_first():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="GitHub repo for omnireach"))
    assert "github" in route.source_ids


def test_auto_falls_back_to_defaults_when_no_hint():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="天气怎么样"))
    assert "web" in route.source_ids
    assert "hackernews" in route.source_ids


def test_quick_mode_narrows_to_web_and_hn():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="anything", mode="quick"))
    assert set(route.source_ids) == {"web", "hackernews"}


def test_route_caps_at_five_sources():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="anything", mode="deep"))
    assert len(route.source_ids) <= 5
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/test_router.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/router.py`**

```python
"""Router — picks which sources to fan out to for a given query."""

from __future__ import annotations

from dataclasses import dataclass

from omnireach.registry import Registry

MAX_SOURCES = 5


@dataclass
class RouteRequest:
    query: str
    explicit_sources: list[str] | None = None  # --on flag
    mode: str = "auto"  # auto | quick | deep


@dataclass
class Route:
    source_ids: list[str]
    rationale: str  # short explanation for --verbose


class Router:
    def __init__(self, registry: Registry) -> None:
        self.registry = registry

    def plan(self, req: RouteRequest) -> Route:
        if req.explicit_sources:
            valid = [s.id for s in self.registry.sources]
            chosen = [s for s in req.explicit_sources if s in valid]
            return Route(source_ids=chosen, rationale="explicit --on")

        if req.mode == "quick":
            return Route(source_ids=["web", "hackernews"], rationale="mode=quick")

        if req.mode == "deep":
            all_ready = [s.id for s in self.registry.sources if s.tier == "ready"]
            return Route(source_ids=all_ready[:MAX_SOURCES], rationale="mode=deep")

        # auto: hint matches first, then default
        hinted = [s.id for s in self.registry.sources_matching_hints(req.query)]
        defaults = [s.id for s in self.registry.default_auto_sources()]
        merged: list[str] = []
        for sid in hinted + defaults:
            if sid not in merged:
                merged.append(sid)
            if len(merged) >= MAX_SOURCES:
                break
        return Route(source_ids=merged, rationale="auto: hints + defaults")
```

- [ ] **Step 4: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/test_router.py -x
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/router.py tests/test_router.py && git commit -m "feat(router): heuristic source selection with --on / mode flags"
```

---

## Task 7: Dispatcher

**Files:**
- Create: `omnireach/dispatcher.py`
- Create: `tests/test_dispatcher.py`

- [ ] **Step 1: Write failing test**

`tests/test_dispatcher.py`:

```python
import asyncio

import pytest

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult
from omnireach.dispatcher import Dispatcher


def _result(source: str) -> SearchResult:
    return SearchResult(
        source=source,
        adapter="t",
        title=f"hit-{source}",
        url=f"https://e.x/{source}",
        ts="2026-05-25T12:00:00Z",
        score=0.5,
    )


class OkAdapter(AdapterBase):
    name = "ok"

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        return [_result(self.name)]


class SlowAdapter(OkAdapter):
    name = "slow"

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        await asyncio.sleep(5)
        return [_result("slow")]


class BoomAdapter(OkAdapter):
    name = "boom"

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        raise AdapterUnavailable("boom", "exploded", hint="reinstall")


async def test_dispatch_aggregates_results():
    d = Dispatcher(timeout=1.0)
    a1 = OkAdapter(); a1.name = "a1"
    a2 = OkAdapter(); a2.name = "a2"
    out, errs = await d.run({"a1": a1, "a2": a2}, "q")
    sources = sorted(r.source for r in out)
    assert sources == ["a1", "a2"]
    assert errs == []


async def test_dispatch_isolates_failures():
    d = Dispatcher(timeout=1.0)
    a = OkAdapter(); a.name = "ok"
    out, errs = await d.run({"ok": a, "boom": BoomAdapter()}, "q")
    assert any(r.source == "ok" for r in out)
    assert any(e.source == "boom" for e in errs)


async def test_dispatch_times_out_one_source_without_blocking_others():
    d = Dispatcher(timeout=0.1)
    a = OkAdapter(); a.name = "ok"
    out, errs = await d.run({"ok": a, "slow": SlowAdapter()}, "q")
    assert any(r.source == "ok" for r in out)
    assert any(e.source == "slow" and "timeout" in e.error.lower() for e in errs)
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/test_dispatcher.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/dispatcher.py`**

```python
"""Dispatcher — concurrent fan-out across adapters, errors isolated."""

from __future__ import annotations

import asyncio

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult, SourceError


class Dispatcher:
    def __init__(self, *, timeout: float = 15.0, per_source_limit: int = 10) -> None:
        self.timeout = timeout
        self.per_source_limit = per_source_limit

    async def run(
        self, adapters: dict[str, AdapterBase], query: str
    ) -> tuple[list[SearchResult], list[SourceError]]:
        async def one(name: str, adapter: AdapterBase) -> tuple[str, list[SearchResult] | Exception]:
            try:
                results = await asyncio.wait_for(
                    adapter.search(query, limit=self.per_source_limit), timeout=self.timeout
                )
                return name, results
            except asyncio.TimeoutError:
                return name, asyncio.TimeoutError(f"timeout after {self.timeout}s")
            except AdapterUnavailable as e:
                return name, e
            except Exception as e:  # noqa: BLE001
                return name, e

        outputs = await asyncio.gather(*[one(n, a) for n, a in adapters.items()])

        all_results: list[SearchResult] = []
        errors: list[SourceError] = []
        for name, payload in outputs:
            if isinstance(payload, list):
                all_results.extend(payload)
            else:
                errors.append(SourceError(source=name, error=str(payload)))
        return all_results, errors
```

- [ ] **Step 4: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/test_dispatcher.py -x
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/dispatcher.py tests/test_dispatcher.py && git commit -m "feat(dispatcher): concurrent fanout with per-source timeout + error isolation"
```

---

## Task 8: Normalizer + Scorer

**Files:**
- Create: `omnireach/normalizer.py`
- Create: `omnireach/scorer.py`
- Create: `tests/test_normalizer_scorer.py`

- [ ] **Step 1: Write failing test**

`tests/test_normalizer_scorer.py`:

```python
from datetime import datetime, timezone

from omnireach.contract import Engagement, SearchEnvelope, SearchResult, SourceError
from omnireach.normalizer import build_envelope
from omnireach.scorer import rank


def _r(source: str, score: float, likes: int = 0, ts: str = "2026-05-25T12:00:00Z") -> SearchResult:
    return SearchResult(
        source=source,
        adapter="t",
        title=f"{source}-{score}",
        url=f"https://e.x/{source}",
        ts=ts,
        score=score,
        engagement=Engagement(likes=likes),
    )


def test_build_envelope_attaches_query_and_ts():
    env = build_envelope(
        query="q",
        results=[_r("hn", 0.8)],
        errors=[SourceError(source="x", error="e")],
    )
    assert env.query == "q"
    assert env.results[0].source == "hn"
    assert env.errors[0].source == "x"
    # ts should be ISO-8601 ending in Z (UTC)
    assert env.ts.endswith("Z") or "+" in env.ts


def test_rank_orders_by_score_desc():
    a = _r("a", 0.3)
    b = _r("b", 0.9)
    c = _r("c", 0.5)
    ranked = rank([a, b, c])
    assert [r.source for r in ranked] == ["b", "c", "a"]


def test_rank_breaks_ties_by_engagement_then_recency():
    older = _r("a", 0.5, likes=10, ts="2026-01-01T00:00:00Z")
    newer = _r("b", 0.5, likes=10, ts="2026-05-25T00:00:00Z")
    more_liked = _r("c", 0.5, likes=999, ts="2026-01-01T00:00:00Z")
    ranked = rank([older, newer, more_liked])
    assert [r.source for r in ranked] == ["c", "b", "a"]
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/test_normalizer_scorer.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/normalizer.py`**

```python
"""Normalizer — wraps adapter outputs into a SearchEnvelope."""

from __future__ import annotations

from datetime import datetime, timezone

from omnireach.contract import SearchEnvelope, SearchResult, SourceError


def build_envelope(
    *, query: str, results: list[SearchResult], errors: list[SourceError]
) -> SearchEnvelope:
    return SearchEnvelope(
        query=query,
        ts=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        results=results,
        errors=errors,
    )
```

- [ ] **Step 4: Implement `omnireach/scorer.py`**

```python
"""Scorer — rank results across sources."""

from __future__ import annotations

from datetime import datetime, timezone

from omnireach.contract import SearchResult


def _ts_to_epoch(ts: str | None) -> float:
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def rank(results: list[SearchResult]) -> list[SearchResult]:
    """Sort by score desc, breaking ties with engagement.likes then ts (newer first)."""

    def key(r: SearchResult) -> tuple[float, int, float]:
        likes = (r.engagement.likes if r.engagement and r.engagement.likes else 0)
        return (-r.score, -likes, -_ts_to_epoch(r.ts))

    return sorted(results, key=key)
```

- [ ] **Step 5: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/test_normalizer_scorer.py -x
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/normalizer.py omnireach/scorer.py tests/test_normalizer_scorer.py && git commit -m "feat(pipeline): envelope normalizer + cross-source scorer"
```

---

## Task 9: CLI shell with `search` subcommand

**Files:**
- Create: `omnireach/cli.py`
- Create: `omnireach/__main__.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

`tests/test_cli.py`:

```python
import json

from click.testing import CliRunner

from omnireach.cli import main


def test_cli_help():
    runner = CliRunner()
    res = runner.invoke(main, ["--help"])
    assert res.exit_code == 0
    assert "search" in res.output


def test_cli_search_on_hackernews_only_smoke(monkeypatch):
    """Smoke test — uses --on hackernews + --offline-fixtures to avoid real network."""
    import omnireach.adapters.hackernews as hn

    async def fake_search(self, query, *, limit=10):
        from omnireach.contract import SearchResult
        return [
            SearchResult(
                source="hackernews",
                adapter="builtin",
                title=f"fake {query}",
                url="https://e.x/1",
                ts="2026-05-25T12:00:00Z",
                score=0.7,
            )
        ]

    monkeypatch.setattr(hn.HackerNewsAdapter, "search", fake_search)

    runner = CliRunner()
    res = runner.invoke(main, ["search", "--on", "hackernews", "--json", "claude"])
    assert res.exit_code == 0, res.output
    parsed = json.loads(res.output)
    assert parsed["query"] == "claude"
    assert parsed["results"][0]["source"] == "hackernews"
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/test_cli.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/cli.py`**

```python
"""omnireach CLI entry."""

from __future__ import annotations

import asyncio
import json
import sys

import click
from rich.console import Console
from rich.table import Table

from omnireach import __version__
from omnireach.dispatcher import Dispatcher
from omnireach.normalizer import build_envelope
from omnireach.registry import load_registry
from omnireach.router import RouteRequest, Router
from omnireach.scorer import rank

console = Console()


@click.group()
@click.version_option(__version__, "-V", "--version")
def main() -> None:
    """omnireach — 全网通搜索 CLI."""


@main.command("search")
@click.argument("query")
@click.option("--on", "on_", help="只用这些源, 逗号分隔. 例: --on hackernews,web")
@click.option("--mode", type=click.Choice(["auto", "quick", "deep"]), default="auto")
@click.option("--limit", type=int, default=10, help="每个源最多返回多少条")
@click.option("--timeout", type=float, default=15.0)
@click.option("--json", "json_out", is_flag=True, help="输出 JSON, 适合下游 pipe")
def search_cmd(query: str, on_: str | None, mode: str, limit: int, timeout: float, json_out: bool) -> None:
    """运行一次搜索."""
    explicit = [s.strip() for s in on_.split(",")] if on_ else None
    reg = load_registry()
    router = Router(reg)
    route = router.plan(RouteRequest(query=query, explicit_sources=explicit, mode=mode))

    adapters = {}
    for sid in route.source_ids:
        try:
            spec = reg.get(sid)
            adapters[sid] = spec.load_adapter_class()()
        except Exception as e:  # noqa: BLE001
            console.print(f"[yellow]skip {sid}: {e}[/yellow]", file=sys.stderr)

    dispatcher = Dispatcher(timeout=timeout, per_source_limit=limit)
    results, errors = asyncio.run(dispatcher.run(adapters, query))
    ranked = rank(results)
    envelope = build_envelope(query=query, results=ranked, errors=errors)

    if json_out:
        click.echo(envelope.model_dump_json())
        return

    table = Table(title=f"omnireach: {query}  ({len(ranked)} hits, {len(errors)} errors)")
    table.add_column("源", style="cyan")
    table.add_column("标题")
    table.add_column("URL", style="dim")
    for r in ranked:
        table.add_row(r.source, r.title[:80], r.url)
    console.print(table)
    for err in errors:
        console.print(f"[red]✗ {err.source}: {err.error}[/red]")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Implement `omnireach/__main__.py`**

```python
from omnireach.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/test_cli.py -x
```

Expected: 2 passed.

- [ ] **Step 6: Manual smoke (still no network — uses monkeypatched test path)**

```bash
cd ~/Projects/omnireach && omnireach --help
```

Expected: shows commands including `search`.

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/cli.py omnireach/__main__.py tests/test_cli.py && git commit -m "feat(cli): top-level Click group + search subcommand"
```

---

## Task 10: Doctor

**Files:**
- Create: `omnireach/doctor.py`
- Create: `tests/test_doctor.py`
- Modify: `omnireach/cli.py` (register doctor command)

- [ ] **Step 1: Write failing test**

`tests/test_doctor.py`:

```python
from click.testing import CliRunner

from omnireach.cli import main
from omnireach.doctor import run_doctor


async def test_run_doctor_returns_status_per_source(monkeypatch):
    statuses = await run_doctor()
    ids = [s.source for s in statuses]
    assert "hackernews" in ids
    hn = next(s for s in statuses if s.source == "hackernews")
    assert hn.ok is True


def test_doctor_cli_runs():
    runner = CliRunner()
    res = runner.invoke(main, ["doctor"])
    assert res.exit_code in (0, 1)  # may be 1 if some sources fail; output must still render
    assert "hackernews" in res.output
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/test_doctor.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/doctor.py`**

```python
"""Doctor — probe each source's readiness."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from omnireach.registry import load_registry


@dataclass
class SourceStatus:
    source: str
    tier: str
    ok: bool
    detail: str = ""


async def run_doctor() -> list[SourceStatus]:
    reg = load_registry()
    statuses: list[SourceStatus] = []
    for spec in reg.sources:
        try:
            cls = spec.load_adapter_class()
            ok = await cls().is_ready()
            statuses.append(SourceStatus(spec.id, spec.tier, ok, "" if ok else "not ready"))
        except Exception as e:  # noqa: BLE001
            statuses.append(SourceStatus(spec.id, spec.tier, False, str(e)))
    return statuses
```

- [ ] **Step 4: Add `doctor` subcommand to `omnireach/cli.py`**

Append (before `if __name__ == "__main__":`):

```python
@main.command("doctor")
def doctor_cmd() -> None:
    """检查每个源的就绪状态."""
    from omnireach.doctor import run_doctor

    statuses = asyncio.run(run_doctor())
    table = Table(title="omnireach doctor")
    table.add_column("源", style="cyan")
    table.add_column("tier", style="magenta")
    table.add_column("ok")
    table.add_column("详情", style="dim")
    any_bad = False
    for s in statuses:
        mark = "✅" if s.ok else "❌"
        if not s.ok:
            any_bad = True
        table.add_row(s.source, s.tier, mark, s.detail)
    console.print(table)
    sys.exit(0 if not any_bad else 1)
```

- [ ] **Step 5: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/test_doctor.py -x
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/doctor.py omnireach/cli.py tests/test_doctor.py && git commit -m "feat(doctor): per-source readiness probe + CLI subcommand"
```

---

## Task 11: Installer (auto-install upstream via pipx)

**Files:**
- Create: `omnireach/installer.py`
- Create: `tests/test_installer.py`

- [ ] **Step 1: Write failing test**

`tests/test_installer.py`:

```python
import shutil
import subprocess

import pytest

from omnireach.installer import (
    InstallError,
    ensure_binary,
    install_pipx_package,
)


def test_ensure_binary_returns_path_when_present(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)
    assert ensure_binary("git") == "/usr/bin/git"


def test_ensure_binary_raises_when_missing(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(InstallError) as exc:
        ensure_binary("not-real-bin", hint="安装它")
    assert "not-real-bin" in str(exc.value)


def test_install_pipx_package_invokes_pipx(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pipx")
    install_pipx_package("agent-reach")
    assert calls and calls[0][:3] == ["pipx", "install", "agent-reach"]


def test_install_pipx_raises_on_failure(monkeypatch):
    def fake_run(args, **kwargs):
        class R:
            returncode = 1
            stdout = ""
            stderr = "boom"

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pipx")
    with pytest.raises(InstallError):
        install_pipx_package("agent-reach")
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/test_installer.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/installer.py`**

```python
"""Installer — auto-install upstream tools the Agent can handle without user input."""

from __future__ import annotations

import shutil
import subprocess


class InstallError(Exception):
    def __init__(self, package: str, reason: str, *, hint: str | None = None) -> None:
        super().__init__(f"install {package} failed: {reason}")
        self.package = package
        self.reason = reason
        self.hint = hint


def ensure_binary(name: str, *, hint: str | None = None) -> str:
    """Return absolute path to a binary on PATH, or raise."""
    path = shutil.which(name)
    if not path:
        raise InstallError(name, f"binary '{name}' not on PATH", hint=hint)
    return path


def install_pipx_package(package: str) -> None:
    ensure_binary("pipx", hint="安装 pipx: brew install pipx 或 python -m pip install --user pipx")
    res = subprocess.run(
        ["pipx", "install", package],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise InstallError(package, res.stderr or res.stdout or "pipx install failed")


def install_npm_global(package: str) -> None:
    ensure_binary("npm", hint="安装 Node.js (>=20): https://nodejs.org/")
    res = subprocess.run(
        ["npm", "install", "-g", package],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise InstallError(package, res.stderr or "npm install -g failed")
```

- [ ] **Step 4: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/test_installer.py -x
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/installer.py tests/test_installer.py && git commit -m "feat(installer): pipx + npm auto-install helpers"
```

---

## Task 12: Web adapter (agent-reach subprocess)

**Files:**
- Create: `omnireach/adapters/web.py`
- Create: `tests/adapters/test_web.py`

- [ ] **Step 1: Write failing test**

`tests/adapters/test_web.py`:

```python
import json
import subprocess

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.web import WebSearchAdapter


async def test_web_search_parses_agent_reach_json(monkeypatch):
    fake_output = json.dumps({
        "results": [
            {
                "title": "claude docs",
                "url": "https://docs.anthropic.com",
                "content": "Claude is...",
                "published_at": "2026-05-01T00:00:00Z",
            }
        ]
    })

    async def fake_subprocess_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake_output.encode(), b"")

        return P()

    import asyncio
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess_exec)
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/agent-reach")

    a = WebSearchAdapter()
    out = await a.search("claude", limit=3)
    assert len(out) == 1
    assert out[0].source == "web"
    assert out[0].url == "https://docs.anthropic.com"


async def test_web_missing_binary_raises_unavailable(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    a = WebSearchAdapter()
    with pytest.raises(AdapterUnavailable):
        await a.search("claude")


async def test_web_is_ready_checks_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/agent-reach")
    a = WebSearchAdapter()
    assert await a.is_ready() is True
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert await a.is_ready() is False
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_web.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/adapters/web.py`**

```python
"""Web search adapter — shells out to agent-reach."""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult


class WebSearchAdapter(AdapterBase):
    name = "web"
    requires = ["agent-reach"]

    async def is_ready(self) -> bool:
        return shutil.which("agent-reach") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("agent-reach"):
            raise AdapterUnavailable(
                "web", "agent-reach not installed", hint="omnireach init  (会自动 pipx install)"
            )

        proc = await asyncio.create_subprocess_exec(
            "agent-reach", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("web", err.decode().strip() or "agent-reach search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("web", f"agent-reach returned non-JSON: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    source="web",
                    adapter="agent-reach",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", "") or item.get("snippet", ""),
                    ts=item.get("published_at") or item.get("ts"),
                    score=0.5,
                    raw=item,
                )
            )
        return results
```

- [ ] **Step 4: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_web.py -x
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/adapters/web.py tests/adapters/test_web.py && git commit -m "feat(adapters): web search via agent-reach subprocess"
```

---

## Task 13: YouTube adapter

**Files:**
- Create: `omnireach/adapters/youtube.py`
- Create: `tests/adapters/test_youtube.py`

- [ ] **Step 1: Write failing test**

`tests/adapters/test_youtube.py`:

```python
import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.youtube import YouTubeAdapter


async def test_youtube_search_parses_agent_reach_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "Claude Code intro",
                "url": "https://youtube.com/watch?v=abc",
                "channel": "Anthropic",
                "transcript": "Welcome…",
                "published_at": "2026-05-01T00:00:00Z",
                "views": 12345,
                "likes": 678,
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0
            async def communicate(self):
                return (fake.encode(), b"")
        return P()

    import asyncio
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/agent-reach")

    out = await YouTubeAdapter().search("claude code", limit=3)
    assert out[0].source == "youtube"
    assert out[0].author == "Anthropic"
    assert out[0].engagement.likes == 678
    assert out[0].engagement.views == 12345


async def test_youtube_missing_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable):
        await YouTubeAdapter().search("x")
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_youtube.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/adapters/youtube.py`**

```python
"""YouTube adapter — shells out to agent-reach (which wraps yt-dlp)."""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


class YouTubeAdapter(AdapterBase):
    name = "youtube"
    requires = ["agent-reach"]

    async def is_ready(self) -> bool:
        return shutil.which("agent-reach") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("agent-reach"):
            raise AdapterUnavailable("youtube", "agent-reach not installed", hint="omnireach init")

        proc = await asyncio.create_subprocess_exec(
            "agent-reach", "youtube", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("youtube", err.decode().strip() or "search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("youtube", f"non-JSON output: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    source="youtube",
                    adapter="agent-reach",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("transcript", "") or item.get("description", ""),
                    author=item.get("channel"),
                    ts=item.get("published_at"),
                    score=0.5,
                    engagement=Engagement(
                        likes=item.get("likes"),
                        views=item.get("views"),
                    ),
                    raw=item,
                )
            )
        return results
```

- [ ] **Step 4: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_youtube.py -x
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/adapters/youtube.py tests/adapters/test_youtube.py && git commit -m "feat(adapters): youtube via agent-reach (yt-dlp)"
```

---

## Task 14: GitHub adapter

**Files:**
- Create: `omnireach/adapters/github.py`
- Create: `tests/adapters/test_github.py`

- [ ] **Step 1: Write failing test**

`tests/adapters/test_github.py`:

```python
import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.github import GitHubAdapter


async def test_github_search_parses_agent_reach_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "Daily-AC/omnireach",
                "url": "https://github.com/Daily-AC/omnireach",
                "description": "全网通搜索 CLI + Skill",
                "stars": 42,
                "kind": "repo",
                "updated_at": "2026-05-25T00:00:00Z",
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0
            async def communicate(self):
                return (fake.encode(), b"")
        return P()

    import asyncio
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/agent-reach")

    out = await GitHubAdapter().search("omnireach", limit=3)
    assert out[0].source == "github"
    assert out[0].engagement.likes == 42  # stars mapped to likes


async def test_github_missing_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable):
        await GitHubAdapter().search("x")
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_github.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/adapters/github.py`**

```python
"""GitHub adapter — shells out to agent-reach."""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


class GitHubAdapter(AdapterBase):
    name = "github"
    requires = ["agent-reach"]

    async def is_ready(self) -> bool:
        return shutil.which("agent-reach") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("agent-reach"):
            raise AdapterUnavailable("github", "agent-reach not installed", hint="omnireach init")

        proc = await asyncio.create_subprocess_exec(
            "agent-reach", "github", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("github", err.decode().strip() or "search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("github", f"non-JSON output: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    source="github",
                    adapter="agent-reach",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("description", "") or item.get("body", ""),
                    ts=item.get("updated_at") or item.get("created_at"),
                    score=0.5,
                    engagement=Engagement(likes=item.get("stars")),
                    raw=item,
                )
            )
        return results
```

- [ ] **Step 4: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_github.py -x
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/adapters/github.py tests/adapters/test_github.py && git commit -m "feat(adapters): github via agent-reach"
```

---

## Task 15: RSS adapter

**Files:**
- Create: `omnireach/adapters/rss.py`
- Create: `tests/adapters/test_rss.py`

- [ ] **Step 1: Write failing test**

`tests/adapters/test_rss.py`:

```python
import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.rss import RSSAdapter


async def test_rss_search_parses_agent_reach_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "Anthropic ships Claude 4.7",
                "url": "https://anthropic.com/blog/4-7",
                "summary": "...",
                "published_at": "2026-05-20T00:00:00Z",
                "feed": "https://anthropic.com/rss",
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0
            async def communicate(self):
                return (fake.encode(), b"")
        return P()

    import asyncio
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/agent-reach")

    out = await RSSAdapter().search("anthropic", limit=3)
    assert out[0].source == "rss"


async def test_rss_missing_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable):
        await RSSAdapter().search("x")
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_rss.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/adapters/rss.py`**

```python
"""RSS adapter — shells out to agent-reach."""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult


class RSSAdapter(AdapterBase):
    name = "rss"
    requires = ["agent-reach"]

    async def is_ready(self) -> bool:
        return shutil.which("agent-reach") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("agent-reach"):
            raise AdapterUnavailable("rss", "agent-reach not installed", hint="omnireach init")

        proc = await asyncio.create_subprocess_exec(
            "agent-reach", "rss", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("rss", err.decode().strip() or "search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("rss", f"non-JSON output: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    source="rss",
                    adapter="agent-reach",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("summary", "") or item.get("content", ""),
                    ts=item.get("published_at"),
                    score=0.4,
                    raw=item,
                )
            )
        return results
```

- [ ] **Step 4: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_rss.py -x
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/adapters/rss.py tests/adapters/test_rss.py && git commit -m "feat(adapters): rss via agent-reach"
```

---

## Task 16: WeChat 公众号 adapter

**Files:**
- Create: `omnireach/adapters/wechat.py`
- Create: `tests/adapters/test_wechat.py`

- [ ] **Step 1: Write failing test**

`tests/adapters/test_wechat.py`:

```python
import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.wechat import WeChatAdapter


async def test_wechat_search_parses_agent_reach_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "Claude 4.7 评测",
                "url": "https://mp.weixin.qq.com/s/xxx",
                "content_markdown": "# Claude 4.7…",
                "account": "AI 前线",
                "published_at": "2026-05-20T00:00:00Z",
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0
            async def communicate(self):
                return (fake.encode(), b"")
        return P()

    import asyncio
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/agent-reach")

    out = await WeChatAdapter().search("claude", limit=3)
    assert out[0].source == "wechat"
    assert out[0].author == "AI 前线"


async def test_wechat_missing_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable):
        await WeChatAdapter().search("x")
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_wechat.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/adapters/wechat.py`**

```python
"""微信公众号 adapter — shells out to agent-reach."""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult


class WeChatAdapter(AdapterBase):
    name = "wechat"
    requires = ["agent-reach"]

    async def is_ready(self) -> bool:
        return shutil.which("agent-reach") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("agent-reach"):
            raise AdapterUnavailable("wechat", "agent-reach not installed", hint="omnireach init")

        proc = await asyncio.create_subprocess_exec(
            "agent-reach", "wechat", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("wechat", err.decode().strip() or "search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("wechat", f"non-JSON output: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    source="wechat",
                    adapter="agent-reach",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content_markdown", "") or item.get("content", ""),
                    author=item.get("account"),
                    ts=item.get("published_at"),
                    score=0.5,
                    raw=item,
                )
            )
        return results
```

- [ ] **Step 4: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_wechat.py -x
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/adapters/wechat.py tests/adapters/test_wechat.py && git commit -m "feat(adapters): wechat 公众号 via agent-reach"
```

---

## Task 17: Bilibili adapter

**Files:**
- Create: `omnireach/adapters/bilibili.py`
- Create: `tests/adapters/test_bilibili.py`

- [ ] **Step 1: Write failing test**

`tests/adapters/test_bilibili.py`:

```python
import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.bilibili import BilibiliAdapter


async def test_bilibili_search_parses_agent_reach_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "Claude Code 教程",
                "url": "https://bilibili.com/video/BVxxxx",
                "subtitle": "字幕全文…",
                "uploader": "技术宅",
                "play_count": 88000,
                "like_count": 4500,
                "published_at": "2026-05-10T00:00:00Z",
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0
            async def communicate(self):
                return (fake.encode(), b"")
        return P()

    import asyncio
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/agent-reach")

    out = await BilibiliAdapter().search("claude", limit=3)
    assert out[0].source == "bilibili"
    assert out[0].engagement.views == 88000
    assert out[0].engagement.likes == 4500


async def test_bilibili_missing_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable):
        await BilibiliAdapter().search("x")
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_bilibili.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/adapters/bilibili.py`**

```python
"""Bilibili (B站) adapter — shells out to agent-reach."""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


class BilibiliAdapter(AdapterBase):
    name = "bilibili"
    requires = ["agent-reach"]

    async def is_ready(self) -> bool:
        return shutil.which("agent-reach") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("agent-reach"):
            raise AdapterUnavailable("bilibili", "agent-reach not installed", hint="omnireach init")

        proc = await asyncio.create_subprocess_exec(
            "agent-reach", "bilibili", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("bilibili", err.decode().strip() or "search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("bilibili", f"non-JSON output: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    source="bilibili",
                    adapter="agent-reach",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("subtitle", "") or item.get("description", ""),
                    author=item.get("uploader"),
                    ts=item.get("published_at"),
                    score=0.5,
                    engagement=Engagement(
                        likes=item.get("like_count"),
                        views=item.get("play_count"),
                    ),
                    raw=item,
                )
            )
        return results
```

- [ ] **Step 4: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/adapters/test_bilibili.py -x
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/adapters/bilibili.py tests/adapters/test_bilibili.py && git commit -m "feat(adapters): bilibili via agent-reach"
```

---

## Task 18: `init` subcommand

**Files:**
- Create: `omnireach/commands/__init__.py` (empty)
- Create: `omnireach/commands/init.py`
- Modify: `omnireach/cli.py` (register init)
- Create: `tests/test_cmd_init.py`

- [ ] **Step 1: Write failing test**

`tests/test_cmd_init.py`:

```python
from click.testing import CliRunner

from omnireach.cli import main


def test_init_installs_agent_reach_when_missing(monkeypatch):
    called = {"args": None}

    def fake_install(pkg):
        called["args"] = pkg

    monkeypatch.setattr("omnireach.installer.install_pipx_package", fake_install)
    monkeypatch.setattr("shutil.which", lambda n: None if n == "agent-reach" else "/usr/bin/" + n)

    runner = CliRunner()
    res = runner.invoke(main, ["init", "--yes"])
    assert res.exit_code == 0, res.output
    assert called["args"] == "agent-reach"
    assert "agent-reach" in res.output


def test_init_skips_when_agent_reach_present(monkeypatch):
    def boom_install(pkg):
        raise AssertionError("should not be called")

    monkeypatch.setattr("omnireach.installer.install_pipx_package", boom_install)
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/" + n)
    runner = CliRunner()
    res = runner.invoke(main, ["init", "--yes"])
    assert res.exit_code == 0, res.output
    assert "已安装" in res.output or "already" in res.output.lower()
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/test_cmd_init.py -x
```

Expected: ImportError or command-not-found.

- [ ] **Step 3: Implement `omnireach/commands/__init__.py` (empty)**

```python
```

- [ ] **Step 4: Implement `omnireach/commands/init.py`**

```python
"""omnireach init — install zero-config upstream dependencies."""

from __future__ import annotations

import shutil

import click
from rich.console import Console

from omnireach import installer

console = Console()


@click.command("init")
@click.option("--yes", "-y", is_flag=True, help="跳过确认")
def init_cmd(yes: bool) -> None:
    """安装零配置源所需的上游工具 (主要是 agent-reach)。"""
    if shutil.which("agent-reach"):
        console.print("[green]✅ agent-reach 已安装[/green]")
        return

    if not yes:
        if not click.confirm("即将通过 pipx 安装 agent-reach (Agent-Reach), 继续?"):
            console.print("[yellow]取消[/yellow]")
            return

    console.print("[cyan]正在 pipx install agent-reach…[/cyan]")
    try:
        installer.install_pipx_package("agent-reach")
    except installer.InstallError as e:
        console.print(f"[red]安装失败: {e}[/red]")
        if e.hint:
            console.print(f"[yellow]提示: {e.hint}[/yellow]")
        raise SystemExit(1)
    console.print("[green]✅ agent-reach 安装完成[/green]")
    console.print("现在试试: [bold]omnireach \"Claude 4.7 怎么样\"[/bold]")
```

- [ ] **Step 5: Register `init` in `omnireach/cli.py`**

Add at top imports (after existing imports):

```python
from omnireach.commands.init import init_cmd
```

Add at bottom (before `if __name__ == "__main__":`):

```python
main.add_command(init_cmd)
```

- [ ] **Step 6: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/test_cmd_init.py -x
```

Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/commands/ omnireach/cli.py tests/test_cmd_init.py && git commit -m "feat(cli): init subcommand auto-installs agent-reach via pipx"
```

---

## Task 19: `sources` subcommand (心愿单)

**Files:**
- Create: `omnireach/commands/sources.py`
- Modify: `omnireach/cli.py` (register)
- Create: `tests/test_cmd_sources.py`

- [ ] **Step 1: Write failing test**

`tests/test_cmd_sources.py`:

```python
from click.testing import CliRunner

from omnireach.cli import main


def test_sources_lists_all_registered():
    runner = CliRunner()
    res = runner.invoke(main, ["sources"])
    assert res.exit_code == 0
    for sid in ["hackernews", "web", "youtube", "github", "rss", "wechat", "bilibili"]:
        assert sid in res.output


def test_sources_groups_by_tier():
    runner = CliRunner()
    res = runner.invoke(main, ["sources"])
    assert "ready" in res.output.lower()
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/test_cmd_sources.py -x
```

Expected: FAIL.

- [ ] **Step 3: Implement `omnireach/commands/sources.py`**

```python
"""omnireach sources — list registered sources grouped by tier."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.table import Table

from omnireach.doctor import run_doctor
from omnireach.registry import load_registry

console = Console()

TIER_ICON = {"ready": "✅", "one_step": "🟡", "heavy": "🔴"}


@click.command("sources")
@click.option("--probe", is_flag=True, help="实际跑 is_ready 探测每个源 (慢一点)")
def sources_cmd(probe: bool) -> None:
    """列出所有源 + 心愿单状态."""
    reg = load_registry()

    statuses: dict[str, bool] = {}
    if probe:
        for s in asyncio.run(run_doctor()):
            statuses[s.source] = s.ok

    by_tier: dict[str, list] = {"ready": [], "one_step": [], "heavy": []}
    for s in reg.sources:
        by_tier.setdefault(s.tier, []).append(s)

    for tier in ["ready", "one_step", "heavy"]:
        items = by_tier.get(tier, [])
        if not items:
            continue
        table = Table(title=f"{TIER_ICON[tier]} {tier} ({len(items)})", show_lines=False)
        table.add_column("id", style="cyan")
        table.add_column("描述")
        if probe:
            table.add_column("probe")
        for s in items:
            row = [s.id, s.description]
            if probe:
                row.append("✅" if statuses.get(s.id) else "❌")
            table.add_row(*row)
        console.print(table)
```

- [ ] **Step 4: Register in `omnireach/cli.py`**

Add to imports:

```python
from omnireach.commands.sources import sources_cmd
```

Add after the `init_cmd` registration:

```python
main.add_command(sources_cmd)
```

- [ ] **Step 5: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/test_cmd_sources.py -x
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/commands/sources.py omnireach/cli.py tests/test_cmd_sources.py && git commit -m "feat(cli): sources subcommand — tier-grouped wishlist"
```

---

## Task 20: Claude Code Skill manifest

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.claude-plugin/skills/omnireach/SKILL.md`
- Create: `tests/test_skill_manifest.py`

- [ ] **Step 1: Write failing test**

`tests/test_skill_manifest.py`:

```python
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


def test_plugin_manifest_is_valid_json():
    data = json.loads((PROJECT_ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert data["name"] == "omnireach"
    assert "skills" in data["components"]


def test_skill_md_exists_and_has_required_frontmatter():
    skill_md = (PROJECT_ROOT / ".claude-plugin" / "skills" / "omnireach" / "SKILL.md").read_text()
    assert skill_md.startswith("---")
    assert "name: omnireach" in skill_md
    assert "description:" in skill_md


def test_skill_md_documents_cli_invocation():
    skill_md = (PROJECT_ROOT / ".claude-plugin" / "skills" / "omnireach" / "SKILL.md").read_text()
    assert "omnireach" in skill_md
    assert "pipx" in skill_md.lower() or "install" in skill_md.lower()
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd ~/Projects/omnireach && pytest tests/test_skill_manifest.py -x
```

Expected: FAIL (files missing).

- [ ] **Step 3: Create `.claude-plugin/plugin.json`**

```json
{
  "name": "omnireach",
  "version": "0.1.0",
  "description": "全网通搜索 Skill: web + Twitter/Reddit/YouTube/B站/小红书/HN/GitHub 一站接入, 中转站用户也能用",
  "author": "Daily-AC",
  "license": "MIT",
  "homepage": "https://github.com/Daily-AC/omnireach",
  "components": {
    "skills": ["./skills/omnireach"]
  }
}
```

- [ ] **Step 4: Create `.claude-plugin/skills/omnireach/SKILL.md`**

```markdown
---
name: omnireach
description: Use when the user needs to search the web or read content from Twitter / Reddit / YouTube / Bilibili / 小红书 / HackerNews / GitHub / 微信公众号 / RSS, especially when the built-in WebSearch is unavailable (proxy/relay stations). Provides a unified search across multiple platforms with a single command.
---

# omnireach — 全网通搜索

omnireach 是一个 CLI 工具，把 web 搜索 + 多平台读取 (Twitter / Reddit / YouTube / B站 / 小红书 / HN / GitHub / 微信公众号 / RSS) 整合到一条命令里。对于用中转站、装不上 Anthropic 原生 WebSearch 的同学，这是一个"全网通"替代品。

## 如何使用

### 第一次用 (用户没装过)

1. 让用户跑: `pipx install omnireach && omnireach init`
2. 装完后, 7 个零配置源 (web / hackernews / youtube / github / rss / 微信公众号 / B站) 就立刻可用
3. 想解锁 Twitter / Reddit / 小红书, 让用户跑: `omnireach sources` 看心愿单, 再 `omnireach setup <source>`

### 搜索

直接调 CLI 拿 JSON:

```bash
omnireach search --json "Claude 4.7 prompt caching 实测"
```

返回标准化 JSON: `{query, ts, results: [{source, title, url, content, score, engagement, raw}], errors}`.

### 限定源

```bash
omnireach search --on twitter,reddit --json "anyrouter 跑路"
omnireach search --on hackernews --json "show hn omnireach"
```

### 模式

```bash
omnireach search --mode quick "...."  # 只查 web + hackernews
omnireach search --mode deep  "...."  # 全部就绪源
```

## 何时用 omnireach 而不是其他工具

- **用 omnireach**: 用户在中转站环境, 或想搜 Twitter/Reddit/小红书/B站 等原生 WebSearch 不擅长的源
- **不用**: 简单的网页打开 (用 WebFetch), 或代码搜索 (用 grep/Grep)
```

- [ ] **Step 5: Run, expect PASS**

```bash
cd ~/Projects/omnireach && pytest tests/test_skill_manifest.py -x
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/omnireach && git add .claude-plugin/ tests/test_skill_manifest.py && git commit -m "feat(skill): Claude Code Skill manifest for omnireach"
```

---

## Task 21: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

```markdown
# omnireach

> 🌐 全网通搜索 — 一个 CLI + Claude Code Skill, 给中转站 Agent 用户补齐 WebSearch + 多平台读取能力。

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)

## 为什么需要 omnireach

中转站 (cliproxy / anyrouter / 各种 OpenAI 兼容代理) 让国内同学绕开付费、能调多模型, 但代价是丢掉了 Anthropic 服务端工具, 其中 **WebSearch** 是损失最重的一项:

- 想搜 Twitter 上的实时讨论? 原生 WebSearch 几乎抓不到
- 想看 Reddit / HN 的深度评论? 拿不到
- 想读 YouTube 字幕、小红书种草、B 站技术视频? 完全不可达

omnireach 把社区里已经成熟的三个上游工具 (**Agent-Reach** / **OpenCLI** / **last30days**) 当可插拔引擎调用, 对外只暴露一个轻量 CLI + 一个 Claude Skill, 实现 **3 分钟内**装好就能搜全网。

## 快速开始

```bash
pipx install omnireach
omnireach init       # 自动装好 agent-reach 等零配置依赖
omnireach "Claude 4.7 prompt caching 实测"
```

### 在 Claude Code 里用

```
/plugin marketplace add Daily-AC/omnireach
/plugin install omnireach
```

然后在对话里直接说: "用 omnireach 搜一下 …"

## 命令

| 命令 | 干嘛 |
|---|---|
| `omnireach "<query>"` 或 `omnireach search "<query>"` | 搜索 |
| `omnireach search --on twitter,reddit "..."` | 指定源 |
| `omnireach search --mode quick "..."` | 只查 web + hn |
| `omnireach search --mode deep "..."` | 查所有就绪源 |
| `omnireach search --json "..."` | 输出 JSON 给下游 pipe |
| `omnireach init` | 安装零配置依赖 |
| `omnireach sources` | 列出所有源 + 心愿单状态 |
| `omnireach doctor` | 健康检查 |

## v0.1 支持的源

✅ **零配置 (7 个)**: `web` · `hackernews` · `youtube` · `github` · `rss` · `wechat` (微信公众号) · `bilibili` (B 站)

🟡 / 🔴 计划中 (v0.2+): `reddit` · `twitter` · `xiaohongshu` (小红书)

## 设计

详见 `docs/superpowers/specs/2026-05-25-omnireach-design.md`.

## License

MIT — 见 [LICENSE](LICENSE).
```

- [ ] **Step 2: Verify pytest still green**

```bash
cd ~/Projects/omnireach && pytest -x
```

Expected: ALL tests pass (no test changed, but sanity check).

- [ ] **Step 3: Manually verify CLI end-to-end (offline-friendly)**

```bash
cd ~/Projects/omnireach && omnireach --help && omnireach sources && omnireach doctor || echo "(doctor may exit 1 if agent-reach not installed locally — that's expected)"
```

Expected: `--help` shows 4 commands (search, init, sources, doctor). `sources` prints 7 rows under "ready". `doctor` prints ✅ for hackernews; ❌ for the rest unless agent-reach installed.

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/omnireach && git add README.md && git commit -m "docs: README for v0.1"
```

- [ ] **Step 5: Final v0.1 tag**

```bash
cd ~/Projects/omnireach && git tag -a v0.1.0-alpha -m "omnireach v0.1.0-alpha — core + 7 zero-config sources + Skill manifest"
cd ~/Projects/omnireach && git log --oneline | head -25
```

Expected: clean linear history of ~21 commits.

---

## Self-review checks performed

- **Spec coverage**: §2 goals (1) bootstrap path → Tasks 1 + 18 + 21; (2) 7 zero-config sources → Tasks 4, 12-17; (3) router + `--on` → Task 6; (4) Agent vs user split — Wizard (full `setup` subcommand) is deferred to v0.2 plan; (5) JSON contract → Task 2; (6) 中文 first → README + CLI strings in Tasks 18-21. §5 architecture → Tasks 2-10. §6 source list → Tasks 4 + 12-17 (all 7 ready-tier sources covered).
- **Placeholder scan**: no TBD/TODO; every code step has the actual code.
- **Type consistency**: `SearchResult` fields used identically across all adapter tasks; `AdapterBase.search(query, *, limit)` signature consistent; `Engagement.likes` / `views` mapped consistently.
- **Deferred (intentional, not gaps)**: `Wizard` (interactive `setup` subcommand) and the 🟡/🔴 sources (reddit/twitter/小红书) belong to v0.2/v0.3 plans, not v0.1.
