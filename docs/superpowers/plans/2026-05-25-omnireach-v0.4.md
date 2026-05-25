# omnireach v0.4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship omnireach v0.4.0-alpha — paid booster (Tavily/Brave/Perplexity) + `~/.omnireach/preferences.toml` + source_trust weighted ranking.

**Architecture:** Three feature slices share one milestone. (1) Boosters reuse `AdapterBase` and live in `omnireach/adapters/`; activation is env-var detection. (2) Preferences are a pydantic v2 model loaded once at CLI startup and merged as defaults before CLI flags. (3) Ranking adds `source_trust` (from `sources.yml`) into the existing `scorer.rank()` formula. SearchResult schema grows `cost` + `raw_score`.

**Tech Stack:** Python 3.11+, pydantic v2, httpx, click, rich, PyYAML, stdlib `tomllib`. No new runtime deps.

---

## File Structure (created/modified by this plan)

**Created:**
- `omnireach/adapters/tavily.py` — Tavily booster
- `omnireach/adapters/brave.py` — Brave Search booster
- `omnireach/adapters/perplexity.py` — Perplexity sonar booster
- `omnireach/preferences.py` — pydantic model + load/save
- `omnireach/secrets_env.py` — dotenv parser, loads `~/.omnireach/secrets.env` into `os.environ`
- `omnireach/commands/preferences.py` — `omnireach preferences {show,edit,reset,path}`
- `tests/adapters/test_tavily.py`
- `tests/adapters/test_brave.py`
- `tests/adapters/test_perplexity.py`
- `tests/test_preferences.py`
- `tests/test_secrets_env.py`
- `tests/test_cmd_preferences.py`

**Modified:**
- `omnireach/contract.py` — `SearchResult` adds `cost: Literal["free","paid"] = "free"` and `raw_score: float = 0.0`
- `omnireach/scorer.py` — new weighted formula `0.4 * recency_norm + 0.6 * source_trust`
- `omnireach/registry.py` — `SourceSpec` adds `trust: float`
- `omnireach/sources.yml` — each source gets `trust:`; add `booster` tier; add 3 booster entries
- `omnireach/cli.py` — startup loads secrets.env + preferences; search defaults pulled from preferences; TTY rows prefix 💎 when `cost == "paid"`
- `omnireach/commands/sources.py` — render new 💎 booster section
- `omnireach/commands/setup.py` — add tavily/brave/perplexity branches
- `omnireach/commands/init.py` — write default `~/.omnireach/preferences.toml` on first run
- `README.md` — booster + preferences sections
- `pyproject.toml` — bump to `0.4.0-alpha`

---

## Task 0: Branch off main

- [ ] **Step 1: Confirm clean main**

```bash
cd ~/Projects/omnireach
git status   # expect: clean (uv.lock untracked is fine)
git log --oneline -1   # expect: v0.3 commit on main
```

- [ ] **Step 2: Branch**

```bash
git checkout -b feat/v0.4-booster-prefs-ranking
```

---

## Task 1: SearchResult schema + scorer trust weighting

**Files:**
- Modify: `omnireach/contract.py`
- Modify: `omnireach/scorer.py`
- Modify: `omnireach/registry.py`
- Modify: `tests/test_normalizer_scorer.py`

- [ ] **Step 1: Write failing scorer test**

Append to `tests/test_normalizer_scorer.py`:

```python
from omnireach.contract import SearchResult
from omnireach.scorer import rank


def _r(source: str, ts: str | None, trust: float, **kw) -> SearchResult:
    return SearchResult(source=source, adapter="t", title=source, url=f"https://x/{source}", ts=ts, **kw)


def test_rank_uses_source_trust_when_recency_equal():
    trust_map = {"hn": 0.85, "youtube": 0.6}
    a = _r("hn", "2026-05-25T00:00:00+00:00", 0.85)
    b = _r("youtube", "2026-05-25T00:00:00+00:00", 0.6)
    out = rank([b, a], trust_map=trust_map)
    assert [r.source for r in out] == ["hn", "youtube"]


def test_rank_uses_recency_when_trust_equal():
    trust_map = {"hn": 0.7, "web": 0.7}
    old = _r("hn", "2020-01-01T00:00:00+00:00", 0.7)
    new = _r("web", "2026-05-25T00:00:00+00:00", 0.7)
    out = rank([old, new], trust_map=trust_map)
    assert [r.source for r in out] == ["web", "hn"]


def test_rank_handles_missing_ts_as_midpoint():
    trust_map = {"hn": 0.7, "web": 0.7}
    no_ts = _r("hn", None, 0.7)
    old = _r("web", "2020-01-01T00:00:00+00:00", 0.7)
    out = rank([old, no_ts], trust_map=trust_map)
    assert [r.source for r in out] == ["hn", "web"]


def test_rank_writes_raw_score():
    trust_map = {"hn": 0.85}
    r = _r("hn", "2026-05-25T00:00:00+00:00", 0.85)
    out = rank([r], trust_map=trust_map)
    assert 0.0 <= out[0].raw_score <= 1.0


def test_searchresult_defaults_cost_free():
    r = SearchResult(source="x", adapter="t", title="t", url="https://x")
    assert r.cost == "free"
    assert r.raw_score == 0.0
```

- [ ] **Step 2: Run tests, confirm fail**

```bash
cd ~/Projects/omnireach
uv run pytest tests/test_normalizer_scorer.py -v
# Expected: 5 new tests fail (rank signature mismatch / missing fields)
```

- [ ] **Step 3: Extend SearchResult schema**

In `omnireach/contract.py`, top of file add `Literal` to typing imports:

```python
from typing import Any, Literal
```

In `SearchResult` add fields after `raw`:

```python
    cost: Literal["free", "paid"] = "free"
    raw_score: float = Field(default=0.0, ge=0.0, le=1.0)
```

- [ ] **Step 4: Extend SourceSpec with trust**

In `omnireach/registry.py`, edit `SourceSpec`:

```python
@dataclass
class SourceSpec:
    id: str
    tier: str  # ready | one_step | heavy | booster
    adapter: str
    description: str
    query_hints: list[str] = field(default_factory=list)
    default_in_auto: bool = False
    trust: float = 0.7
    deps_auto: list[Dep] = field(default_factory=list)
    deps_manual: list[Dep] = field(default_factory=list)
```

Then in `load_registry()` (search file for it; if absent at this point, the function lives in same file constructing SourceSpec from yaml), wire `trust=entry.get("trust", 0.7)`.

- [ ] **Step 5: Rewrite scorer**

Replace `omnireach/scorer.py` body with:

```python
"""Scorer — rank results across sources by recency + source_trust."""

from __future__ import annotations

from datetime import datetime

from omnireach.contract import SearchResult

W_RECENCY = 0.4
W_TRUST = 0.6


def _ts_to_epoch(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _normalize_recency(results: list[SearchResult]) -> list[float]:
    epochs = [_ts_to_epoch(r.ts) for r in results]
    real = [e for e in epochs if e is not None]
    if not real:
        return [0.5] * len(results)
    lo, hi = min(real), max(real)
    span = hi - lo if hi > lo else 1.0
    return [0.5 if e is None else (e - lo) / span for e in epochs]


def rank(results: list[SearchResult], *, trust_map: dict[str, float] | None = None) -> list[SearchResult]:
    trust_map = trust_map or {}
    rec = _normalize_recency(results)
    for r, rn in zip(results, rec, strict=True):
        t = trust_map.get(r.source, 0.7)
        r.raw_score = W_RECENCY * rn + W_TRUST * t
    return sorted(results, key=lambda r: -r.raw_score)
```

- [ ] **Step 6: Update CLI call site**

In `omnireach/cli.py`, replace:

```python
ranked = rank(results)
```

with:

```python
trust_map = {s.id: s.trust for s in reg.sources}
ranked = rank(results, trust_map=trust_map)
```

- [ ] **Step 7: Run tests**

```bash
uv run pytest tests/test_normalizer_scorer.py -v
# Expected: all pass
uv run pytest -x
# Expected: full suite green (existing tests still pass)
```

- [ ] **Step 8: Commit**

```bash
git add omnireach/contract.py omnireach/scorer.py omnireach/registry.py omnireach/cli.py tests/test_normalizer_scorer.py
git commit -m "feat(v0.4): SearchResult.cost/raw_score + scorer source_trust weighting"
```

---

## Task 2: sources.yml — trust field on all sources + booster tier

**Files:**
- Modify: `omnireach/sources.yml`
- Modify: `tests/test_registry.py`

- [ ] **Step 1: Add trust to every existing source entry**

Edit `omnireach/sources.yml`. For each source block add a `trust:` line. Use:

```
hackernews: 0.85
web:        0.70
youtube:    0.60
github:     0.90
rss:        0.75
wechat:     0.55
bilibili:   0.55
reddit:     0.70
twitter:    0.60
xiaohongshu: 0.50
```

Example diff for hackernews:

```yaml
- id: hackernews
  tier: ready
  adapter: omnireach.adapters.hackernews.HackerNewsAdapter
  description: HackerNews 全文搜索
  query_hints: [hn, hackernews, "show hn"]
  default_in_auto: true
  trust: 0.85
  deps: { auto: [], manual: [] }
```

- [ ] **Step 2: Append three booster entries at end of sources.yml**

```yaml
- id: tavily
  tier: booster
  adapter: omnireach.adapters.tavily.TavilyAdapter
  description: Tavily Search API (付费, web 类增强)
  query_hints: []
  default_in_auto: true
  trust: 0.85
  deps:
    auto: []
    manual:
      - step: "去 https://tavily.com 注册并复制 API Key"
        verify: "echo $TAVILY_API_KEY 非空"

- id: brave
  tier: booster
  adapter: omnireach.adapters.brave.BraveAdapter
  description: Brave Search API (付费, 隐私友好 web 搜索)
  query_hints: []
  default_in_auto: true
  trust: 0.80
  deps:
    auto: []
    manual:
      - step: "去 https://brave.com/search/api 注册并复制 Key"
        verify: "echo $BRAVE_API_KEY 非空"

- id: perplexity
  tier: booster
  adapter: omnireach.adapters.perplexity.PerplexityAdapter
  description: Perplexity Sonar (付费, AI 检索摘要)
  query_hints: []
  default_in_auto: true
  trust: 0.90
  deps:
    auto: []
    manual:
      - step: "去 https://perplexity.ai/settings/api 注册并复制 Key"
        verify: "echo $PERPLEXITY_API_KEY 非空"
```

- [ ] **Step 3: Write registry test**

Append to `tests/test_registry.py`:

```python
def test_registry_loads_trust_field():
    from omnireach.registry import load_registry
    reg = load_registry()
    by_id = {s.id: s for s in reg.sources}
    assert by_id["hackernews"].trust == 0.85
    assert by_id["xiaohongshu"].trust == 0.50


def test_registry_loads_booster_tier():
    from omnireach.registry import load_registry
    reg = load_registry()
    boosters = [s for s in reg.sources if s.tier == "booster"]
    assert {s.id for s in boosters} == {"tavily", "brave", "perplexity"}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_registry.py -v
# Expected: pass (adapters not yet existing is fine — load_adapter_class is lazy)
uv run pytest -x
# Expected: full suite green
```

- [ ] **Step 5: Commit**

```bash
git add omnireach/sources.yml tests/test_registry.py
git commit -m "feat(v0.4): add trust field + booster tier in sources.yml"
```

---

## Task 3: secrets.env loader

**Files:**
- Create: `omnireach/secrets_env.py`
- Create: `tests/test_secrets_env.py`

- [ ] **Step 1: Write tests**

Create `tests/test_secrets_env.py`:

```python
import os
from pathlib import Path

import pytest

from omnireach.secrets_env import load_secrets_env


def test_load_simple_kv(tmp_path: Path, monkeypatch):
    f = tmp_path / "secrets.env"
    f.write_text("FOO=bar\nBAZ=qux\n")
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    load_secrets_env(f)
    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "qux"


def test_load_strips_quotes(tmp_path: Path, monkeypatch):
    f = tmp_path / "secrets.env"
    f.write_text('FOO="bar baz"\nQUX=\'q\'\n')
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("QUX", raising=False)
    load_secrets_env(f)
    assert os.environ["FOO"] == "bar baz"
    assert os.environ["QUX"] == "q"


def test_load_ignores_comments_and_blank(tmp_path: Path, monkeypatch):
    f = tmp_path / "secrets.env"
    f.write_text("# comment\n\nFOO=bar\n")
    monkeypatch.delenv("FOO", raising=False)
    load_secrets_env(f)
    assert os.environ["FOO"] == "bar"


def test_load_does_not_override_existing_env(tmp_path: Path, monkeypatch):
    f = tmp_path / "secrets.env"
    f.write_text("FOO=fromfile\n")
    monkeypatch.setenv("FOO", "fromenv")
    load_secrets_env(f)
    assert os.environ["FOO"] == "fromenv"


def test_load_missing_file_is_noop(tmp_path: Path):
    load_secrets_env(tmp_path / "missing.env")  # no raise


def test_load_warns_on_loose_permissions(tmp_path: Path, capsys):
    f = tmp_path / "secrets.env"
    f.write_text("FOO=bar\n")
    f.chmod(0o644)
    load_secrets_env(f)
    captured = capsys.readouterr()
    assert "permission" in captured.err.lower() or "权限" in captured.err
```

- [ ] **Step 2: Implement loader**

Create `omnireach/secrets_env.py`:

```python
"""dotenv-style loader for ~/.omnireach/secrets.env.

Intentionally minimal: KEY=VALUE per line, quotes stripped, comments skipped,
existing env wins. Avoids python-dotenv dependency.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path


def load_secrets_env(path: Path) -> None:
    """Read path and merge into os.environ (without overriding existing keys)."""
    if not path.exists():
        return

    try:
        mode = path.stat().st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            print(
                f"warning: {path} permissions are loose ({oct(mode & 0o777)}); "
                "请运行 `chmod 600` 限制可读权限",
                file=sys.stderr,
            )
    except OSError:
        pass

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
```

- [ ] **Step 3: Wire into CLI startup**

In `omnireach/cli.py`, after the imports add:

```python
from pathlib import Path
from omnireach.secrets_env import load_secrets_env

_SECRETS_PATH = Path.home() / ".omnireach" / "secrets.env"
load_secrets_env(_SECRETS_PATH)
```

(Put this right before `console = Console()` so it runs once at module import.)

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_secrets_env.py -v
# Expected: all pass
uv run pytest -x
```

- [ ] **Step 5: Commit**

```bash
git add omnireach/secrets_env.py omnireach/cli.py tests/test_secrets_env.py
git commit -m "feat(v0.4): secrets.env loader for booster API keys"
```

---

## Task 4: preferences.py — pydantic model + load/save

**Files:**
- Create: `omnireach/preferences.py`
- Create: `tests/test_preferences.py`

- [ ] **Step 1: Write tests**

Create `tests/test_preferences.py`:

```python
from pathlib import Path

import pytest

from omnireach.preferences import (
    Preferences,
    load_preferences,
    write_default_preferences,
    DEFAULT_PREFERENCES_TOML,
)


def test_default_preferences_values():
    p = Preferences()
    assert "web" in p.defaults.on
    assert p.defaults.lang == "zh-CN"
    assert p.output.format == "tty"
    assert p.output.max_results_per_source == 8
    assert p.boosters.auto_enable is True
    assert p.trust_overrides == {}


def test_load_preferences_missing_returns_default(tmp_path: Path):
    p = load_preferences(tmp_path / "nonexistent.toml")
    assert isinstance(p, Preferences)
    assert p.defaults.lang == "zh-CN"


def test_load_preferences_valid(tmp_path: Path):
    f = tmp_path / "preferences.toml"
    f.write_text(
        """
[defaults]
on = ["hackernews"]
lang = "en-US"

[output]
max_results_per_source = 20

[boosters]
auto_enable = false

[trust_overrides]
web = 0.95
"""
    )
    p = load_preferences(f)
    assert p.defaults.on == ["hackernews"]
    assert p.defaults.lang == "en-US"
    assert p.output.max_results_per_source == 20
    assert p.boosters.auto_enable is False
    assert p.trust_overrides == {"web": 0.95}


def test_load_preferences_invalid_falls_back_with_warning(tmp_path: Path, capsys):
    f = tmp_path / "preferences.toml"
    f.write_text("this is { not valid toml ===")
    p = load_preferences(f)
    assert isinstance(p, Preferences)
    err = capsys.readouterr().err
    assert "preferences" in err.lower()


def test_write_default_preferences_roundtrip(tmp_path: Path):
    f = tmp_path / "preferences.toml"
    write_default_preferences(f)
    assert f.exists()
    assert "[defaults]" in f.read_text()
    p = load_preferences(f)
    assert p.defaults.lang == "zh-CN"


def test_default_toml_has_comments():
    assert "#" in DEFAULT_PREFERENCES_TOML
```

- [ ] **Step 2: Implement**

Create `omnireach/preferences.py`:

```python
"""User preferences: ~/.omnireach/preferences.toml."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Defaults(BaseModel):
    model_config = ConfigDict(extra="forbid")
    on: list[str] = Field(default_factory=lambda: ["web", "hackernews", "reddit", "twitter"])
    exclude: list[str] = Field(default_factory=list)
    lang: str = "zh-CN"


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: str = "tty"
    max_results_per_source: int = 8


class Boosters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    auto_enable: bool = True


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    defaults: Defaults = Field(default_factory=Defaults)
    output: Output = Field(default_factory=Output)
    boosters: Boosters = Field(default_factory=Boosters)
    trust_overrides: dict[str, float] = Field(default_factory=dict)


DEFAULT_PREFERENCES_TOML = """\
# omnireach preferences — 编辑后用 `omnireach preferences show` 验证

[defaults]
# 默认参与 fanout 的源（CLI --on 会覆盖）
on      = ["web", "hackernews", "reddit", "twitter"]
exclude = []                  # 始终排除的源
lang    = "zh-CN"             # 透传到 web/wechat 等

[output]
format                 = "tty"   # tty | json
max_results_per_source = 8

[boosters]
# false 表示即使配了 Key 也不调用付费源
auto_enable = true

[trust_overrides]
# 覆盖 sources.yml 的默认 source_trust（0.0-1.0）
# web = 0.80
"""


def preferences_path() -> Path:
    return Path.home() / ".omnireach" / "preferences.toml"


def load_preferences(path: Path | None = None) -> Preferences:
    path = path or preferences_path()
    if not path.exists():
        return Preferences()
    try:
        data = tomllib.loads(path.read_text())
        return Preferences.model_validate(data)
    except (tomllib.TOMLDecodeError, ValidationError) as e:
        print(
            f"warning: preferences.toml invalid ({e}); 使用默认值。"
            f"编辑文件: {path}",
            file=sys.stderr,
        )
        return Preferences()


def write_default_preferences(path: Path | None = None) -> None:
    path = path or preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_PREFERENCES_TOML)
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_preferences.py -v
uv run pytest -x
```

- [ ] **Step 4: Commit**

```bash
git add omnireach/preferences.py tests/test_preferences.py
git commit -m "feat(v0.4): preferences.toml model + load/save"
```

---

## Task 5: Tavily booster adapter

**Files:**
- Create: `omnireach/adapters/tavily.py`
- Create: `tests/adapters/test_tavily.py`

- [ ] **Step 1: Write tests**

Create `tests/adapters/test_tavily.py`:

```python
import asyncio
from unittest.mock import patch

import httpx
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.tavily import TavilyAdapter


@pytest.fixture
def fixture_payload():
    return {
        "results": [
            {
                "title": "Claude 4.7 review",
                "url": "https://example.com/a",
                "content": "snippet",
                "published_date": "2026-05-20T10:00:00Z",
            },
            {
                "title": "Anthropic release notes",
                "url": "https://example.com/b",
                "content": "another",
                "published_date": "2026-05-22T08:30:00Z",
            },
        ]
    }


def _mock_transport(status: int, json_body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body or {})
    return httpx.MockTransport(handler)


def test_is_ready_false_without_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    a = TavilyAdapter()
    assert asyncio.run(a.is_ready()) is False


def test_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")
    a = TavilyAdapter()
    assert asyncio.run(a.is_ready()) is True


def test_search_returns_results_with_cost_paid(monkeypatch, fixture_payload):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")
    a = TavilyAdapter()
    with patch("omnireach.adapters.tavily.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = httpx.AsyncClient(
            transport=_mock_transport(200, fixture_payload)
        )
        out = asyncio.run(a.search("claude 4.7", limit=5))
    assert len(out) == 2
    assert out[0].source == "tavily"
    assert out[0].cost == "paid"
    assert out[0].title == "Claude 4.7 review"


def test_search_raises_on_401(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "bad")
    a = TavilyAdapter()
    with patch("omnireach.adapters.tavily.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = httpx.AsyncClient(
            transport=_mock_transport(401)
        )
        with pytest.raises(AdapterUnavailable):
            asyncio.run(a.search("q"))


def test_search_raises_without_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    a = TavilyAdapter()
    with pytest.raises(AdapterUnavailable):
        asyncio.run(a.search("q"))
```

- [ ] **Step 2: Implement**

Create `omnireach/adapters/tavily.py`:

```python
"""Tavily Search API booster (paid)."""

from __future__ import annotations

import os

import httpx

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult

TAVILY_URL = "https://api.tavily.com/search"


class TavilyAdapter(AdapterBase):
    name = "tavily"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bool(os.environ.get("TAVILY_API_KEY"))

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        key = os.environ.get("TAVILY_API_KEY")
        if not key:
            raise AdapterUnavailable("tavily", "TAVILY_API_KEY 未设置", hint="omnireach setup tavily")
        payload = {"api_key": key, "query": query, "max_results": limit}
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.post(TAVILY_URL, json=payload)
            except httpx.HTTPError as e:
                raise AdapterUnavailable("tavily", f"http error: {e}") from e
        if resp.status_code == 401:
            raise AdapterUnavailable("tavily", "API Key 无效 (401)")
        if resp.status_code == 429:
            raise AdapterUnavailable("tavily", "rate limited (429)")
        if resp.status_code >= 500:
            raise AdapterUnavailable("tavily", f"upstream {resp.status_code}")
        data = resp.json()
        results: list[SearchResult] = []
        for hit in data.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    source="tavily",
                    adapter="tavily-api",
                    title=hit.get("title") or "",
                    url=hit.get("url") or "",
                    content=hit.get("content") or "",
                    ts=hit.get("published_date"),
                    cost="paid",
                    raw=hit,
                )
            )
        return results
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/adapters/test_tavily.py -v
uv run pytest -x
```

- [ ] **Step 4: Commit**

```bash
git add omnireach/adapters/tavily.py tests/adapters/test_tavily.py
git commit -m "feat(v0.4): Tavily booster adapter"
```

---

## Task 6: Brave booster adapter

**Files:**
- Create: `omnireach/adapters/brave.py`
- Create: `tests/adapters/test_brave.py`

- [ ] **Step 1: Write tests**

Create `tests/adapters/test_brave.py`:

```python
import asyncio
from unittest.mock import patch

import httpx
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.brave import BraveAdapter


@pytest.fixture
def fixture_payload():
    return {
        "web": {
            "results": [
                {
                    "title": "Brave 1",
                    "url": "https://example.com/1",
                    "description": "desc 1",
                    "age": "2026-05-22T10:00:00",
                },
                {
                    "title": "Brave 2",
                    "url": "https://example.com/2",
                    "description": "desc 2",
                },
            ]
        }
    }


def _mock_transport(status: int, json_body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body or {})
    return httpx.MockTransport(handler)


def test_is_ready_false_without_key(monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    assert asyncio.run(BraveAdapter().is_ready()) is False


def test_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "BSA-x")
    assert asyncio.run(BraveAdapter().is_ready()) is True


def test_search_returns_results(monkeypatch, fixture_payload):
    monkeypatch.setenv("BRAVE_API_KEY", "BSA-x")
    a = BraveAdapter()
    with patch("omnireach.adapters.brave.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = httpx.AsyncClient(
            transport=_mock_transport(200, fixture_payload)
        )
        out = asyncio.run(a.search("q", limit=5))
    assert len(out) == 2
    assert out[0].source == "brave"
    assert out[0].cost == "paid"
    assert out[0].title == "Brave 1"


def test_search_raises_on_401(monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "bad")
    a = BraveAdapter()
    with patch("omnireach.adapters.brave.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = httpx.AsyncClient(
            transport=_mock_transport(401)
        )
        with pytest.raises(AdapterUnavailable):
            asyncio.run(a.search("q"))


def test_search_raises_without_key(monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(BraveAdapter().search("q"))
```

- [ ] **Step 2: Implement**

Create `omnireach/adapters/brave.py`:

```python
"""Brave Search API booster (paid)."""

from __future__ import annotations

import os

import httpx

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveAdapter(AdapterBase):
    name = "brave"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bool(os.environ.get("BRAVE_API_KEY"))

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        key = os.environ.get("BRAVE_API_KEY")
        if not key:
            raise AdapterUnavailable("brave", "BRAVE_API_KEY 未设置", hint="omnireach setup brave")
        headers = {"Accept": "application/json", "X-Subscription-Token": key}
        params = {"q": query, "count": limit}
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(BRAVE_URL, headers=headers, params=params)
            except httpx.HTTPError as e:
                raise AdapterUnavailable("brave", f"http error: {e}") from e
        if resp.status_code == 401:
            raise AdapterUnavailable("brave", "API Key 无效 (401)")
        if resp.status_code == 429:
            raise AdapterUnavailable("brave", "rate limited (429)")
        if resp.status_code >= 500:
            raise AdapterUnavailable("brave", f"upstream {resp.status_code}")
        hits = resp.json().get("web", {}).get("results", [])[:limit]
        return [
            SearchResult(
                source="brave",
                adapter="brave-api",
                title=h.get("title") or "",
                url=h.get("url") or "",
                content=h.get("description") or "",
                ts=h.get("age"),
                cost="paid",
                raw=h,
            )
            for h in hits
        ]
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/adapters/test_brave.py -v
uv run pytest -x
```

- [ ] **Step 4: Commit**

```bash
git add omnireach/adapters/brave.py tests/adapters/test_brave.py
git commit -m "feat(v0.4): Brave Search booster adapter"
```

---

## Task 7: Perplexity booster adapter

**Files:**
- Create: `omnireach/adapters/perplexity.py`
- Create: `tests/adapters/test_perplexity.py`

- [ ] **Step 1: Write tests**

Create `tests/adapters/test_perplexity.py`:

```python
import asyncio
from unittest.mock import patch

import httpx
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.perplexity import PerplexityAdapter


@pytest.fixture
def fixture_payload():
    return {
        "id": "x",
        "choices": [
            {
                "message": {
                    "content": "## Summary\n\nClaude 4.7 looks fast.\n\nSources:\n[1] anthropic.com\n[2] news.ycombinator.com"
                }
            }
        ],
        "citations": [
            "https://anthropic.com/news/claude-4-7",
            "https://news.ycombinator.com/item?id=1",
        ],
    }


def _mock_transport(status: int, json_body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body or {})
    return httpx.MockTransport(handler)


def test_is_ready_false_without_key(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    assert asyncio.run(PerplexityAdapter().is_ready()) is False


def test_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-x")
    assert asyncio.run(PerplexityAdapter().is_ready()) is True


def test_search_returns_citations_as_results(monkeypatch, fixture_payload):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-x")
    a = PerplexityAdapter()
    with patch("omnireach.adapters.perplexity.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = httpx.AsyncClient(
            transport=_mock_transport(200, fixture_payload)
        )
        out = asyncio.run(a.search("claude 4.7", limit=5))
    assert len(out) == 2
    assert out[0].source == "perplexity"
    assert out[0].cost == "paid"
    assert out[0].url == "https://anthropic.com/news/claude-4-7"
    assert "fast" in out[0].content.lower() or out[0].content  # summary surfaces


def test_search_raises_on_401(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "bad")
    a = PerplexityAdapter()
    with patch("omnireach.adapters.perplexity.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = httpx.AsyncClient(
            transport=_mock_transport(401)
        )
        with pytest.raises(AdapterUnavailable):
            asyncio.run(a.search("q"))


def test_search_raises_without_key(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(PerplexityAdapter().search("q"))
```

- [ ] **Step 2: Implement**

Create `omnireach/adapters/perplexity.py`:

```python
"""Perplexity Sonar booster (paid)."""

from __future__ import annotations

import os

import httpx

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult

PPLX_URL = "https://api.perplexity.ai/chat/completions"
PPLX_MODEL = "sonar-pro"


class PerplexityAdapter(AdapterBase):
    name = "perplexity"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bool(os.environ.get("PERPLEXITY_API_KEY"))

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        key = os.environ.get("PERPLEXITY_API_KEY")
        if not key:
            raise AdapterUnavailable("perplexity", "PERPLEXITY_API_KEY 未设置", hint="omnireach setup perplexity")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {
            "model": PPLX_MODEL,
            "messages": [{"role": "user", "content": query}],
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(PPLX_URL, headers=headers, json=body)
            except httpx.HTTPError as e:
                raise AdapterUnavailable("perplexity", f"http error: {e}") from e
        if resp.status_code == 401:
            raise AdapterUnavailable("perplexity", "API Key 无效 (401)")
        if resp.status_code == 429:
            raise AdapterUnavailable("perplexity", "rate limited (429)")
        if resp.status_code >= 500:
            raise AdapterUnavailable("perplexity", f"upstream {resp.status_code}")
        data = resp.json()
        summary = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        citations = data.get("citations") or []
        results: list[SearchResult] = []
        for i, url in enumerate(citations[:limit]):
            results.append(
                SearchResult(
                    source="perplexity",
                    adapter="perplexity-api",
                    title=f"[{i+1}] {url}",
                    url=url,
                    content=summary if i == 0 else "",
                    cost="paid",
                    raw={"citation_index": i, "summary": summary},
                )
            )
        return results
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/adapters/test_perplexity.py -v
uv run pytest -x
```

- [ ] **Step 4: Commit**

```bash
git add omnireach/adapters/perplexity.py tests/adapters/test_perplexity.py
git commit -m "feat(v0.4): Perplexity Sonar booster adapter"
```

---

## Task 8: `omnireach sources` shows 💎 booster section

**Files:**
- Modify: `omnireach/commands/sources.py`
- Modify: `tests/test_cmd_sources.py`

- [ ] **Step 1: Read current sources command**

```bash
cat omnireach/commands/sources.py
cat tests/test_cmd_sources.py
```

- [ ] **Step 2: Add booster rendering**

In `omnireach/commands/sources.py`, locate where tiers are grouped (search for `ready` / `one_step` / `heavy`). Add a fourth tier handler. The function should now group sources into four lists by `spec.tier`:

```python
TIER_LABELS = {
    "ready":    ("✅", "ready"),
    "one_step": ("🟡", "一步配置"),
    "heavy":    ("🔴", "重配置"),
    "booster":  ("💎", "付费增强"),
}
```

For each booster, also display key status. After computing the booster list:

```python
import os

def _booster_key_env(source_id: str) -> str:
    return {
        "tavily": "TAVILY_API_KEY",
        "brave": "BRAVE_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY",
    }[source_id]


def _format_booster_entry(source_id: str) -> str:
    has_key = bool(os.environ.get(_booster_key_env(source_id)))
    suffix = "✓ 已配" if has_key else "未配"
    return f"{source_id} ({suffix})"
```

When printing the `booster` tier line, use these formatted entries.

(If the existing command iterates tier order from a list, add `"booster"` last in that list. If it has hard-coded sections, append a new section block after the heavy block.)

- [ ] **Step 3: Update test**

In `tests/test_cmd_sources.py`, add:

```python
def test_sources_command_shows_booster_section(monkeypatch, capsys):
    from click.testing import CliRunner
    from omnireach.cli import main

    monkeypatch.setenv("TAVILY_API_KEY", "x")
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)

    runner = CliRunner()
    result = runner.invoke(main, ["sources"])
    assert result.exit_code == 0
    out = result.output
    assert "💎" in out or "付费增强" in out
    assert "tavily" in out
    assert "已配" in out
    assert "未配" in out
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_cmd_sources.py -v
uv run pytest -x
```

- [ ] **Step 5: Commit**

```bash
git add omnireach/commands/sources.py tests/test_cmd_sources.py
git commit -m "feat(v0.4): omnireach sources shows 💎 booster section with key status"
```

---

## Task 9: `omnireach preferences` subcommand

**Files:**
- Create: `omnireach/commands/preferences.py`
- Create: `tests/test_cmd_preferences.py`
- Modify: `omnireach/cli.py`

- [ ] **Step 1: Write tests**

Create `tests/test_cmd_preferences.py`:

```python
from pathlib import Path

import pytest
from click.testing import CliRunner

from omnireach.cli import main


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def test_preferences_path_prints_expected_path(tmp_home):
    runner = CliRunner()
    result = runner.invoke(main, ["preferences", "path"])
    assert result.exit_code == 0
    assert str(tmp_home / ".omnireach" / "preferences.toml") in result.output


def test_preferences_show_prints_defaults_when_no_file(tmp_home):
    runner = CliRunner()
    result = runner.invoke(main, ["preferences", "show"])
    assert result.exit_code == 0
    assert "zh-CN" in result.output


def test_preferences_reset_creates_file(tmp_home):
    runner = CliRunner()
    result = runner.invoke(main, ["preferences", "reset"])
    assert result.exit_code == 0
    p = tmp_home / ".omnireach" / "preferences.toml"
    assert p.exists()
    assert "[defaults]" in p.read_text()


def test_preferences_reset_backs_up_existing(tmp_home):
    p = tmp_home / ".omnireach" / "preferences.toml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# my edits\n[defaults]\nlang = 'en-US'\n")
    runner = CliRunner()
    result = runner.invoke(main, ["preferences", "reset"])
    assert result.exit_code == 0
    backup = p.with_suffix(".toml.bak")
    assert backup.exists()
    assert "en-US" in backup.read_text()
```

- [ ] **Step 2: Implement command module**

Create `omnireach/commands/preferences.py`:

```python
"""`omnireach preferences {show,edit,reset,path}`."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import click

from omnireach.preferences import (
    load_preferences,
    preferences_path,
    write_default_preferences,
)


@click.group("preferences")
def preferences_cmd() -> None:
    """查看/编辑用户偏好 (~/.omnireach/preferences.toml)."""


@preferences_cmd.command("path")
def _path() -> None:
    click.echo(str(preferences_path()))


@preferences_cmd.command("show")
def _show() -> None:
    p = load_preferences()
    click.echo(json.dumps(p.model_dump(), indent=2, ensure_ascii=False))


@preferences_cmd.command("edit")
def _edit() -> None:
    path = preferences_path()
    if not path.exists():
        write_default_preferences(path)
    editor = os.environ.get("EDITOR") or ("vi" if shutil.which("vi") else "")
    if not editor:
        click.echo("没有 $EDITOR 也没有 vi，直接编辑文件吧:", err=True)
        click.echo(str(path), err=True)
        return
    subprocess.call([editor, str(path)])


@preferences_cmd.command("reset")
def _reset() -> None:
    path = preferences_path()
    if path.exists():
        backup = path.with_suffix(".toml.bak")
        shutil.copy2(path, backup)
        click.echo(f"已备份到 {backup}")
    write_default_preferences(path)
    click.echo(f"已写入默认配置到 {path}")
```

- [ ] **Step 3: Register in CLI**

In `omnireach/cli.py`, after existing `from omnireach.commands.sources import sources_cmd` add:

```python
from omnireach.commands.preferences import preferences_cmd
```

And at the bottom where commands attach to `main`, add:

```python
main.add_command(preferences_cmd)
```

(Search for `main.add_command(sources_cmd)` or similar pattern; place beside it.)

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_cmd_preferences.py -v
uv run pytest -x
```

- [ ] **Step 5: Commit**

```bash
git add omnireach/commands/preferences.py omnireach/cli.py tests/test_cmd_preferences.py
git commit -m "feat(v0.4): omnireach preferences {show,edit,reset,path} subcommand"
```

---

## Task 10: `omnireach setup {tavily,brave,perplexity}` + init writes default preferences + TTY 💎 prefix

**Files:**
- Modify: `omnireach/commands/setup.py`
- Modify: `omnireach/commands/init.py`
- Modify: `omnireach/cli.py`
- Modify: `tests/test_cmd_setup.py`
- Modify: `tests/test_cmd_init.py`

- [ ] **Step 1: Booster setup wizard**

In `omnireach/commands/setup.py`, locate the per-source dispatch (likely a dict / match on `source_id`). Add three branches that all reuse a common helper:

```python
from pathlib import Path
import os
import stat
import click

BOOSTER_GUIDES = {
    "tavily": {
        "env": "TAVILY_API_KEY",
        "signup_url": "https://tavily.com",
        "label": "Tavily Search API",
        "note": "免费层每月 1000 次查询",
    },
    "brave": {
        "env": "BRAVE_API_KEY",
        "signup_url": "https://brave.com/search/api",
        "label": "Brave Search API",
        "note": "免费层每月 2000 次查询",
    },
    "perplexity": {
        "env": "PERPLEXITY_API_KEY",
        "signup_url": "https://perplexity.ai/settings/api",
        "label": "Perplexity Sonar",
        "note": "按 token 计费 (sonar-pro)",
    },
}


def _setup_booster(source_id: str) -> None:
    g = BOOSTER_GUIDES[source_id]
    click.echo(f"{g['label']} 是付费 API ({g['note']})")
    click.echo(f"Agent 能做的:")
    click.echo(f"  ✅ 把你粘贴的 Key 写入 ~/.omnireach/secrets.env (chmod 600)")
    click.echo(f"你需要做的:")
    click.echo(f"  👤 去 {g['signup_url']} 注册/登录, 复制 API Key")
    if not click.confirm("开始吗?", default=True):
        return
    key = click.prompt(f"粘贴 {g['env']}", hide_input=True).strip()
    if not key:
        click.echo("空 Key, 取消", err=True)
        return
    secrets_path = Path.home() / ".omnireach" / "secrets.env"
    secrets_path.parent.mkdir(parents=True, exist_ok=True)
    existing = secrets_path.read_text() if secrets_path.exists() else ""
    lines = [ln for ln in existing.splitlines() if not ln.startswith(f"{g['env']}=")]
    lines.append(f"{g['env']}={key}")
    secrets_path.write_text("\n".join(lines) + "\n")
    secrets_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    click.echo(f"✓ 已写入 {secrets_path}")
```

In the existing dispatch where each source has its own setup path, add:

```python
elif source_id in BOOSTER_GUIDES:
    _setup_booster(source_id)
```

- [ ] **Step 2: Init writes default preferences**

In `omnireach/commands/init.py`, find where it does initial filesystem setup (likely creates `~/.omnireach/`). Add after that block:

```python
from omnireach.preferences import preferences_path, write_default_preferences

pref_path = preferences_path()
if not pref_path.exists():
    write_default_preferences(pref_path)
    click.echo(f"  ✅ 已写入默认偏好: {pref_path}")
```

- [ ] **Step 3: TTY 💎 prefix on paid results**

In `omnireach/cli.py`, find the search command's TTY rendering loop:

```python
for r in ranked:
    table.add_row(r.source, r.title[:80], r.url)
```

Replace with:

```python
for r in ranked:
    source_label = f"💎 {r.source}" if r.cost == "paid" else r.source
    table.add_row(source_label, r.title[:80], r.url)
```

- [ ] **Step 4: Update tests**

In `tests/test_cmd_init.py`, add:

```python
def test_init_writes_default_preferences(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    p = tmp_path / ".omnireach" / "preferences.toml"
    assert p.exists()
    assert "[defaults]" in p.read_text()
```

In `tests/test_cmd_setup.py`, add:

```python
def test_setup_tavily_writes_secrets_env(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "tavily"], input="y\ntvly-abc123\n")
    assert result.exit_code == 0
    secrets = tmp_path / ".omnireach" / "secrets.env"
    assert secrets.exists()
    assert "TAVILY_API_KEY=tvly-abc123" in secrets.read_text()
    import stat as _stat
    mode = secrets.stat().st_mode & 0o777
    assert mode == 0o600
```

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -x
# Expected: full suite green
```

- [ ] **Step 6: Commit**

```bash
git add omnireach/commands/setup.py omnireach/commands/init.py omnireach/cli.py tests/test_cmd_setup.py tests/test_cmd_init.py
git commit -m "feat(v0.4): booster setup wizard + init writes preferences + TTY 💎 prefix"
```

---

## Task 11: README + version bump + tag

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`

- [ ] **Step 1: Bump version**

In `pyproject.toml` change `version = "0.3.0-alpha"` to `version = "0.4.0-alpha"`.

In `omnireach/__init__.py` change `__version__ = "0.3.0-alpha"` to `__version__ = "0.4.0-alpha"`.

- [ ] **Step 2: Update README sources table**

In `README.md`, locate the sources table (under `## 支持的源`). Append rows:

```
| 💎 tavily     | 付费 (Tavily Search API)        | env `TAVILY_API_KEY`     |
| 💎 brave      | 付费 (Brave Search API)         | env `BRAVE_API_KEY`      |
| 💎 perplexity | 付费 (Perplexity Sonar)         | env `PERPLEXITY_API_KEY` |
```

- [ ] **Step 3: Add v0.4 section to README**

Append a new section after the sources table:

```markdown
## 💎 付费 booster (v0.4)

omnireach 默认完全免费。如果你愿意配置付费 API Key，结果质量会更高：

```bash
omnireach setup tavily       # 引导拿 Key + 写入 ~/.omnireach/secrets.env
omnireach setup brave
omnireach setup perplexity
```

检测到 Key 后自动启用。结果元数据 `cost="paid"`，TTY 显示前缀 💎，便于审计。

要禁用：编辑 `~/.omnireach/preferences.toml` 设 `[boosters] auto_enable = false`。

## ⚙️ 用户偏好 (v0.4)

`~/.omnireach/preferences.toml` 可配置默认源、语言、输出格式、source_trust 覆盖。

```bash
omnireach preferences show     # 查看当前配置
omnireach preferences edit     # 用 $EDITOR 编辑
omnireach preferences reset    # 重置 (备份原文件到 .bak)
omnireach preferences path     # 打印文件位置
```
```

- [ ] **Step 4: Verify install + smoke**

```bash
uv pip install -e . --reinstall
omnireach --version    # expect 0.4.0-alpha
omnireach sources      # expect 💎 section shown
uv run pytest          # full green
```

- [ ] **Step 5: Commit + push**

```bash
git add README.md pyproject.toml omnireach/__init__.py
git commit -m "docs(v0.4): README updates + version bump to 0.4.0-alpha"
git push -u origin feat/v0.4-booster-prefs-ranking
```

- [ ] **Step 6: PR → squash merge → tag**

```bash
gh pr create --title "feat: omnireach v0.4 — paid booster + preferences + ranking" --body "$(cat <<'EOF'
## Summary
- Paid booster tier (Tavily / Brave / Perplexity) with env-var detection and `cost="paid"` metadata
- `~/.omnireach/preferences.toml` user preference layer with show/edit/reset/path subcommands
- source_trust weighted ranking: `score = 0.4·recency_norm + 0.6·source_trust`

## Test plan
- [x] `uv run pytest` green
- [x] `omnireach sources` shows 💎 section with key status
- [x] `omnireach setup tavily` writes secrets.env with chmod 600
- [x] `omnireach preferences show` prints merged defaults
- [x] Paid results render with 💎 prefix in TTY output

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --squash --delete-branch
git checkout main && git pull
git tag v0.4.0-alpha && git push origin v0.4.0-alpha
```

---

## Self-review notes

- **Spec coverage:** §2 (booster) → tasks 2, 5, 6, 7, 8, 10. §3 (preferences) → tasks 4, 9, 10. §4 (ranking) → task 1. §5 (schema) → task 1. §6 (file list) all touched. §7 (testing) per-task. §8 non-goals respected (no usage tracking, no TUI editor). §9 risks addressed (cost metadata, timeout, manual tomllib, trust_overrides).
- **Placeholder scan:** all code blocks complete, no TODO/TBD.
- **Type consistency:** `rank(results, trust_map=...)` signature consistent across task 1 + cli usage. `SearchResult.cost` literal `"free"|"paid"` consistent across task 1 + adapters 5/6/7 + cli renderer in task 10.
- **Ordering:** Tasks 5-7 depend on Task 1 (cost field) and Task 2 (sources.yml entry); Task 8/9/10 depend on 5-7 + 4. Task 11 is final integration.
