# omnireach v0.6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Spec: `docs/superpowers/specs/2026-05-26-omnireach-v0.6-design.md`.

**Goal:** Ship v0.6.0-alpha — wechat/bilibili Exa-derived adapters + per-source timeout + dispatcher error classification + verify-contracts script + README cross-CLI line.

**Architecture:** wechat/bilibili reuse the ExaAdapter httpx template with `includeDomains` filter; both consume the same `EXA_API_KEY`. Dispatcher gains per-adapter `asyncio.wait_for` with resolved timeout (source.timeout_seconds → CLI flag → 30s). SourceError gains `category: "unavailable" | "failed"`; TTY only prints failed.

**Tech Stack:** Python 3.11+, pydantic v2, httpx, click. No new deps.

---

## File Structure

**Created**:
- `tests/adapters/test_wechat.py` (rewritten with Exa fixtures)
- `tests/adapters/test_bilibili.py` (rewritten)
- `scripts/verify-adapter-contracts.sh`

**Rewritten**:
- `omnireach/adapters/wechat.py` (Exa httpx + includeDomains)
- `omnireach/adapters/bilibili.py` (Exa httpx + includeDomains)

**Modified**:
- `omnireach/sources.yml` — wechat/bilibili wip→booster; add `timeout_seconds` to several
- `omnireach/registry.py` — SourceSpec adds `timeout_seconds: float | None = None`
- `omnireach/contract.py` — SourceError adds `category: Literal["unavailable","failed"]`
- `omnireach/dispatcher.py` — per-source timeout + category fill
- `omnireach/cli.py` — _BOOSTER_KEY_ENV adds wechat/bilibili; TTY skips unavailable; footer; --timeout help
- `omnireach/doctor.py` — ENV_FOR_BOOSTER same
- `omnireach/commands/sources.py` — wip section silent when empty
- `omnireach/commands/setup.py` — wechat/bilibili routed to booster handler (shared with exa)
- `README.md` — "Works with" line
- `pyproject.toml` + `omnireach/__init__.py` — 0.6.0-alpha
- Tests touched: test_registry, test_router, test_doctor, test_cmd_setup, test_cmd_sources, test_dispatcher

---

## Task 0: Branch (already done)

Branch `feat/v0.6-derived-boosters-and-ux` checked out from main `f091794`.

---

## Task 1: SourceError category + dispatcher classification

**Files:**
- Modify: `omnireach/contract.py`
- Modify: `omnireach/dispatcher.py`
- Modify: `tests/test_dispatcher.py` (probably exists; if not, create)

- [ ] **Step 1: Failing tests**

Append/replace in `tests/test_dispatcher.py`:

```python
import asyncio
import pytest

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult
from omnireach.dispatcher import Dispatcher


class _OkAdapter(AdapterBase):
    name = "ok"
    async def is_ready(self):
        return True
    async def search(self, query, *, limit=10):
        return [SearchResult(source="ok", adapter="t", title="x", url="https://x")]


class _UnavailableAdapter(AdapterBase):
    name = "u"
    async def is_ready(self):
        return False
    async def search(self, query, *, limit=10):
        raise AdapterUnavailable("u", "missing key")


class _FailedAdapter(AdapterBase):
    name = "f"
    async def is_ready(self):
        return True
    async def search(self, query, *, limit=10):
        raise ValueError("kaboom")


def test_dispatcher_classifies_unavailable():
    d = Dispatcher(timeout=5.0, per_source_limit=5)
    results, errors = asyncio.run(d.run({"u": _UnavailableAdapter()}, "q"))
    assert results == []
    assert len(errors) == 1
    assert errors[0].category == "unavailable"


def test_dispatcher_classifies_failed():
    d = Dispatcher(timeout=5.0, per_source_limit=5)
    results, errors = asyncio.run(d.run({"f": _FailedAdapter()}, "q"))
    assert len(errors) == 1
    assert errors[0].category == "failed"


def test_dispatcher_classifies_timeout_as_failed():
    class _Slow(AdapterBase):
        name = "slow"
        async def is_ready(self):
            return True
        async def search(self, query, *, limit=10):
            await asyncio.sleep(2)
            return []

    d = Dispatcher(timeout=0.1, per_source_limit=5)
    results, errors = asyncio.run(d.run({"slow": _Slow()}, "q"))
    assert len(errors) == 1
    assert errors[0].category == "failed"
    assert "timeout" in errors[0].error.lower()
```

- [ ] **Step 2: Update `omnireach/contract.py` SourceError**

```python
from typing import Literal

class SourceError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    error: str
    category: Literal["unavailable", "failed"] = "failed"
```

- [ ] **Step 3: Update `omnireach/dispatcher.py`**

Read existing structure first. The patch in concept:

```python
# In dispatcher's per-source try/except block:
try:
    result = await asyncio.wait_for(adapter.search(query, limit=...), timeout=resolved_timeout)
    ...
except AdapterUnavailable as e:
    errors.append(SourceError(source=sid, error=str(e), category="unavailable"))
except asyncio.TimeoutError:
    errors.append(SourceError(source=sid, error="timeout", category="failed"))
except Exception as e:
    errors.append(SourceError(source=sid, error=str(e), category="failed"))
```

The `resolved_timeout` parameter is introduced in Task 2; for this task, just keep dispatcher's existing single timeout (`self.timeout`) but add per-source resolution support that the registry/sources.yml will fill in next task. If easier: do both T1 and T2 in this commit, since they touch the same `dispatcher.py` body. Plan-wise treat as one logical change.

- [ ] **Step 4: Tests + commit**

```bash
uv run pytest tests/test_dispatcher.py -v
uv run pytest -x
git add omnireach/contract.py omnireach/dispatcher.py tests/test_dispatcher.py
git commit -m "feat(v0.6): SourceError.category + dispatcher classifies unavailable vs failed"
```

---

## Task 2: Per-source timeout

**Files:**
- Modify: `omnireach/sources.yml`
- Modify: `omnireach/registry.py`
- Modify: `omnireach/dispatcher.py`
- Modify: `tests/test_registry.py`, `tests/test_dispatcher.py`

- [ ] **Step 1: Extend SourceSpec**

In `omnireach/registry.py`:

```python
@dataclass
class SourceSpec:
    ...
    timeout_seconds: float | None = None
```

In `load_registry()`, wire `timeout_seconds=entry.get("timeout_seconds")` (raw float or None, no default fallback at this layer).

- [ ] **Step 2: sources.yml add timeout_seconds**

| source | timeout_seconds |
|---|---|
| hackernews | 10 |
| youtube | 20 |
| github | 15 |
| rss | 15 |
| reddit | 20 |
| twitter | 30 |
| xiaohongshu | 30 |
| tavily | 10 |
| brave | 10 |
| perplexity | 30 |
| exa | 15 |
| wechat | 15 |
| bilibili | 15 |

Add the line under each block.

- [ ] **Step 3: Dispatcher resolution**

Modify Dispatcher so each per-source task resolves its timeout via lookup:

```python
def _resolved_timeout(self, source_id: str) -> float:
    spec_timeout = self.timeouts_by_source.get(source_id)
    return spec_timeout if spec_timeout is not None else self.timeout
```

Constructor accepts `timeouts_by_source: dict[str, float | None] | None = None`.

In `omnireach/cli.py` where Dispatcher is constructed, pass `timeouts_by_source={s.id: s.timeout_seconds for s in reg.sources}`.

- [ ] **Step 4: Update tests**

In `tests/test_registry.py` add:

```python
def test_sources_yml_per_source_timeout():
    from omnireach.registry import load_registry
    reg = load_registry()
    by_id = {s.id: s for s in reg.sources}
    assert by_id["hackernews"].timeout_seconds == 10.0
    assert by_id["twitter"].timeout_seconds == 30.0
```

In `tests/test_dispatcher.py` add:

```python
def test_dispatcher_uses_per_source_timeout():
    class _Slow(AdapterBase):
        name = "slow"
        async def is_ready(self): return True
        async def search(self, q, *, limit=10):
            await asyncio.sleep(2)
            return []

    d = Dispatcher(timeout=10.0, per_source_limit=5,
                   timeouts_by_source={"slow": 0.1})
    results, errors = asyncio.run(d.run({"slow": _Slow()}, "q"))
    assert len(errors) == 1
    assert errors[0].category == "failed"
```

- [ ] **Step 5: CLI --timeout help string**

In `omnireach/cli.py`:

```python
@click.option("--timeout", type=float, default=30.0,
              help="全局默认 timeout (秒); 被 sources.yml 中各源的 timeout_seconds 覆盖")
```

- [ ] **Step 6: Tests + commit**

```bash
uv run pytest -x
git add omnireach/registry.py omnireach/sources.yml omnireach/dispatcher.py omnireach/cli.py tests/test_registry.py tests/test_dispatcher.py
git commit -m "feat(v0.6): per-source timeout_seconds in sources.yml"
```

---

## Task 3: wechat adapter Exa-derived

**Files:**
- Rewrite: `omnireach/adapters/wechat.py`
- Create: `tests/adapters/test_wechat.py`
- Modify: `omnireach/sources.yml` (tier wip→booster)

- [ ] **Step 1: Failing tests** in `tests/adapters/test_wechat.py`:

```python
import asyncio
from unittest.mock import patch

import httpx
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.wechat import WeChatAdapter


def _mock_transport(status, body=None):
    def handler(request):
        return httpx.Response(status, json=body or {})
    return httpx.MockTransport(handler)


def test_is_ready_false_without_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    assert asyncio.run(WeChatAdapter().is_ready()) is False


def test_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    assert asyncio.run(WeChatAdapter().is_ready()) is True


def test_search_sends_include_domains(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    captured = {}

    def handler(request):
        captured["body"] = request.read()
        return httpx.Response(200, json={"results": [
            {"title": "公众号 1", "url": "https://mp.weixin.qq.com/s/abc",
             "publishedDate": "2026-05-22T10:00:00Z", "text": "正文"}
        ]})

    real_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("omnireach.adapters.wechat.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(WeChatAdapter().search("q", limit=5))
    import json
    body = json.loads(captured["body"])
    assert body["includeDomains"] == ["mp.weixin.qq.com"]
    assert len(out) == 1
    assert out[0].source == "wechat"
    assert out[0].cost == "paid"


def test_search_raises_on_401(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "bad")
    real_client = httpx.AsyncClient(transport=_mock_transport(401))
    with patch("omnireach.adapters.wechat.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        with pytest.raises(AdapterUnavailable):
            asyncio.run(WeChatAdapter().search("q"))


def test_search_raises_without_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(WeChatAdapter().search("q"))
```

- [ ] **Step 2: Rewrite `omnireach/adapters/wechat.py`**:

```python
"""WeChat 公众号 adapter — Exa domain-filtered search (booster, needs EXA_API_KEY)."""

from __future__ import annotations

import os

import httpx

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult

EXA_URL = "https://api.exa.ai/search"
DOMAINS = ["mp.weixin.qq.com"]


class WeChatAdapter(AdapterBase):
    name = "wechat"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bool(os.environ.get("EXA_API_KEY"))

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        key = os.environ.get("EXA_API_KEY")
        if not key:
            raise AdapterUnavailable("wechat", "EXA_API_KEY 未设置", hint="omnireach setup wechat")
        headers = {"x-api-key": key, "Content-Type": "application/json"}
        body = {"query": query, "numResults": limit, "type": "auto",
                "includeDomains": DOMAINS}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(EXA_URL, json=body, headers=headers)
            except httpx.HTTPError as e:
                raise AdapterUnavailable("wechat", f"http error: {e}") from e
        if resp.status_code == 401:
            raise AdapterUnavailable("wechat", "API Key 无效 (401)")
        if resp.status_code == 429:
            raise AdapterUnavailable("wechat", "rate limited (429)")
        if resp.status_code >= 500:
            raise AdapterUnavailable("wechat", f"upstream {resp.status_code}")
        data = resp.json()
        results: list[SearchResult] = []
        for hit in data.get("results", [])[:limit]:
            results.append(SearchResult(
                source="wechat",
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

- [ ] **Step 3: sources.yml**

In `omnireach/sources.yml`, find wechat entry, change:
- `tier: wip` → `tier: booster`
- `default_in_auto: false` → `default_in_auto: true`
- description → `微信公众号 (Exa domain-filtered, 需 EXA_API_KEY)`
- add `query_hints: [微信, 公众号, wechat]`
- ensure `trust: 0.65`
- replace deps to `manual: [{step: "去 https://exa.ai 拿 EXA_API_KEY", verify: "echo $EXA_API_KEY 非空"}]`

- [ ] **Step 4: Tests + commit**

```bash
uv run pytest tests/adapters/test_wechat.py -v
uv run pytest -x
git add omnireach/adapters/wechat.py omnireach/sources.yml tests/adapters/test_wechat.py
git commit -m "feat(v0.6): wechat adapter via Exa domain-filtered search (wip → booster)"
```

---

## Task 4: bilibili adapter Exa-derived

Mirror Task 3 with file `omnireach/adapters/bilibili.py` + `tests/adapters/test_bilibili.py`. Difference:
- Class `BilibiliAdapter`, name `"bilibili"`
- `DOMAINS = ["bilibili.com", "www.bilibili.com"]`
- Test fixture URL `https://www.bilibili.com/video/BVabc`
- query_hints: `[b站, bilibili, 哔哩哔哩]`
- trust: 0.60

Otherwise identical structure. Commit:
```
git commit -m "feat(v0.6): bilibili adapter via Exa domain-filtered search (wip → booster)"
```

---

## Task 5: CLI + doctor + setup wire wechat/bilibili to EXA_API_KEY

**Files:**
- Modify: `omnireach/cli.py` (_BOOSTER_KEY_ENV + setup augment)
- Modify: `omnireach/doctor.py` (ENV_FOR_BOOSTER)
- Modify: `omnireach/commands/setup.py` (wechat/bilibili route to booster handler)
- Modify: `tests/test_cli.py`, `tests/test_doctor.py`, `tests/test_cmd_setup.py`

- [ ] **Step 1: cli.py**

```python
_BOOSTER_KEY_ENV = {
    "tavily": "TAVILY_API_KEY",
    "brave": "BRAVE_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "exa": "EXA_API_KEY",
    "wechat": "EXA_API_KEY",
    "bilibili": "EXA_API_KEY",
}
```

- [ ] **Step 2: doctor.py** — same dict gets the new entries.

- [ ] **Step 3: setup.py**

In BOOSTER_GUIDES, ADD entries for wechat and bilibili that point to Exa setup (share signup_url, env, label):

```python
"wechat": {
    "env": "EXA_API_KEY",
    "signup_url": "https://exa.ai",
    "label": "微信公众号 (via Exa domain filter)",
    "note": "复用 Exa Key; 一个 Key 同时点亮 exa + wechat + bilibili",
},
"bilibili": {
    "env": "EXA_API_KEY",
    "signup_url": "https://exa.ai",
    "label": "B站 (via Exa domain filter)",
    "note": "复用 Exa Key; 一个 Key 同时点亮 exa + wechat + bilibili",
},
```

Remove the `_setup_wip(source_id)` call branch for wechat/bilibili since they're no longer wip. Keep `_setup_wip` function as the dispatch path for any future wip-tagged source.

- [ ] **Step 4: Tests update**

In `tests/test_cli.py`, add:

```python
def test_search_augment_includes_wechat_bilibili(monkeypatch):
    from omnireach.cli import _augment_with_active_boosters
    from omnireach.registry import load_registry
    monkeypatch.setenv("EXA_API_KEY", "x")
    for k in ("TAVILY_API_KEY", "BRAVE_API_KEY", "PERPLEXITY_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    reg = load_registry()
    out = _augment_with_active_boosters(["hackernews"], reg, explicit_sources=None)
    assert "wechat" in out
    assert "bilibili" in out
    assert "exa" in out
```

In `tests/test_doctor.py`, add wechat/bilibili to the booster Key check:

```python
def test_doctor_marks_wechat_ok_with_exa_key(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    monkeypatch.setenv("EXA_API_KEY", "x")
    statuses = asyncio.run(run_doctor())
    wc = next(s for s in statuses if s.id == "wechat")
    assert wc.ok is True
```

In `tests/test_cmd_setup.py`, update the existing `test_setup_wechat_is_wip` — wechat is no longer wip. Replace with:

```python
def test_setup_wechat_routes_to_exa_booster(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "wechat"], input="y\nexa-test\n")
    assert result.exit_code == 0
    assert "EXA_API_KEY" in result.output or "Exa" in result.output
```

Also remove the wip section assertion in `tests/test_cmd_sources.py test_sources_command_shows_wip_section` since after v0.6 there are no wip sources. Replace with a test that wip tier renders only if non-empty.

- [ ] **Step 5: Tests + commit**

```bash
uv run pytest -x
git add omnireach/cli.py omnireach/doctor.py omnireach/commands/setup.py tests/test_cli.py tests/test_doctor.py tests/test_cmd_setup.py
git commit -m "feat(v0.6): wire wechat/bilibili to shared EXA_API_KEY (cli/doctor/setup)"
```

---

## Task 6: TTY silent unavailable + footer

**Files:**
- Modify: `omnireach/cli.py` (search_cmd TTY rendering)
- Modify: `omnireach/commands/sources.py` (wip section silent when empty)
- Modify: `tests/test_cli.py`, `tests/test_cmd_sources.py`

- [ ] **Step 1: Failing test in tests/test_cli.py**

```python
def test_tty_skips_unavailable_errors_and_prints_footer(monkeypatch, capsys):
    """Unavailable sources must not produce ✗ red rows; instead a footer hint."""
    from click.testing import CliRunner
    from omnireach.cli import main

    # Force no env vars / no binaries → all non-HN sources go unavailable
    monkeypatch.setattr("shutil.which", lambda b: None)
    for env in ("TAVILY_API_KEY", "BRAVE_API_KEY", "PERPLEXITY_API_KEY", "EXA_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["search", "vibe coding", "--limit", "3", "--timeout", "10"])
    out = result.output
    # No red ✗ rows for unavailable sources
    # (we test absence by looking for booster source names like "tavily" preceded by ✗)
    assert "✗ tavily" not in out
    assert "✗ exa" not in out
    # Footer mentions unconfigured + doctor
    assert "未配置" in out or "doctor" in out
```

- [ ] **Step 2: Patch search_cmd TTY block**

In `omnireach/cli.py` find the TTY rendering loop:

```python
for err in errors:
    console.print(f"[red]✗ {err.source}: {err.error}[/red]")
```

Replace with:

```python
failed = [e for e in errors if e.category == "failed"]
unavailable = [e for e in errors if e.category == "unavailable"]
for err in failed:
    console.print(f"[red]✗ {err.source}: {err.error}[/red]")
if unavailable:
    n = len(unavailable)
    console.print(f"[dim]ℹ️  {n} 个源未配置 (跑 `omnireach doctor` 查看修复建议)[/dim]")
```

- [ ] **Step 3: commands/sources.py wip silent when empty**

In the tier-iteration loop, skip rendering wip section if the wip group is empty:

```python
groups = {tier: [] for tier in TIER_ICON}
for spec in reg.sources:
    groups[spec.tier].append(spec)

for tier in ORDER:                          # existing render order
    items = groups[tier]
    if tier == "wip" and not items:
        continue                            # silent when no wip sources
    ...
```

- [ ] **Step 4: Tests + commit**

```bash
uv run pytest -x
git add omnireach/cli.py omnireach/commands/sources.py tests/test_cli.py tests/test_cmd_sources.py
git commit -m "feat(v0.6): TTY skips unavailable errors + footer hint; sources wip silent when empty"
```

---

## Task 7: verify-adapter-contracts.sh + README cross-CLI line

**Files:**
- Create: `scripts/verify-adapter-contracts.sh`
- Modify: `README.md`

- [ ] **Step 1: Create script**

`scripts/verify-adapter-contracts.sh`:

```bash
#!/usr/bin/env bash
# verify-adapter-contracts.sh
# Checks that each adapter's CLI argv shape is still valid for the upstream binary's --help.
# Skips checks for binaries not installed. Exits 0 if all installed binaries match, 1 otherwise.

set -uo pipefail

declare -A ADAPTERS=(
    ["yt-dlp:ytsearch"]="--flat-playlist --dump-json --no-warnings"
    ["gh:search repos"]="--json"
    ["gh:search issues"]="--json"
    ["rdt-cli:search"]="--json --limit"
    ["opencli:twitter search"]="--format --limit"
    ["opencli:xiaohongshu search"]="--format --limit"
)

EXIT=0

for key in "${!ADAPTERS[@]}"; do
    binary="${key%%:*}"
    subcmd="${key#*:}"
    flags="${ADAPTERS[$key]}"
    if ! command -v "$binary" >/dev/null 2>&1; then
        echo "⏭️  $binary not installed, skipping ($subcmd)"
        continue
    fi
    help_out=$("$binary" $subcmd --help 2>&1 || true)
    bad=()
    for flag in $flags; do
        if ! echo "$help_out" | grep -q -- "$flag"; then
            bad+=("$flag")
        fi
    done
    if [[ ${#bad[@]} -gt 0 ]]; then
        echo "❌ $binary $subcmd: missing flags: ${bad[*]}"
        EXIT=1
    else
        echo "✅ $binary $subcmd: argv OK"
    fi
done

exit $EXIT
```

Make executable: `chmod +x scripts/verify-adapter-contracts.sh`.

- [ ] **Step 2: README "Works with" line**

Find the README header / features area (likely under "## 快速开始" or at top). Insert after the project tagline:

```markdown
> **Works with**: Claude Code · Antigravity (`agy`) · 任何识别 `.claude-plugin/` manifest 的 Agent CLI. v0.5.1 实测过 `agy plugin install` 走通完整流程.
```

- [ ] **Step 3: Commit**

```bash
git add scripts/verify-adapter-contracts.sh README.md
git commit -m "feat(v0.6): verify-adapter-contracts.sh + README cross-CLI line"
```

---

## Task 8: Version bump + ship

- [ ] **Step 1: Bump**

`pyproject.toml`: `0.5.2-alpha` → `0.6.0-alpha`
`omnireach/__init__.py`: same

- [ ] **Step 2: Final pytest**

```bash
uv run pytest -x
```

All green.

- [ ] **Step 3: Commit + push + PR + merge + tag + release**

```bash
git add pyproject.toml omnireach/__init__.py
git commit -m "chore(v0.6): bump to 0.6.0-alpha"
git push -u origin feat/v0.6-derived-boosters-and-ux

gh pr create --title "feat: omnireach v0.6 — derived boosters (wechat/bilibili) + per-source timeout + UX cleanup" --body "$(cat <<'EOF'
## Summary
- **wechat / bilibili** moved from 🚧 wip to 💎 booster (Exa domain-filtered search, share `EXA_API_KEY`)
- **Per-source `timeout_seconds`** in sources.yml; dispatcher resolves per-adapter timeout (HN 10s, OpenCLI 30s, etc.)
- **Dispatcher error classification**: `AdapterUnavailable` → silent in TTY, footer hint pointing to `omnireach doctor`. JSON output retains all errors with `category` field.
- **verify-adapter-contracts.sh**: dev tool that diffs adapter argv vs upstream `--help`, prevents the v0.3 contract drift class of bug
- **README**: explicit cross-CLI compatibility line (Claude Code / Antigravity / .claude-plugin)

Source: `docs/superpowers/specs/2026-05-26-omnireach-v0.6-design.md` + lessons retro `docs/retrospectives/2026-05-26-v0.3-v0.5-lessons.md`.

## Test plan
- [x] dispatcher unit tests cover unavailable / failed / timeout categories
- [x] per-source timeout resolution test
- [x] wechat + bilibili adapter tests (mock httpx + assert includeDomains body)
- [x] TTY skip-unavailable + footer test
- [x] Full suite green

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"

gh pr merge --squash --delete-branch
git checkout main && git pull
git tag v0.6.0-alpha && git push origin v0.6.0-alpha

gh release create v0.6.0-alpha --title "omnireach v0.6.0-alpha" --notes "Derived boosters (wechat/bilibili via Exa) + per-source timeout + dispatcher error classification + verify-contracts script + cross-CLI README line. See PR #8."
gh release edit v0.6.0-alpha --latest
```

If `git checkout main` complains about uv.lock drift: `git stash` → checkout → `git stash drop`.

- [ ] **Step 4: Verify**

```bash
git log --oneline -3
git tag -l | tail
uv run omnireach --version          # 0.6.0-alpha
uv run omnireach sources            # wechat/bilibili in 💎 booster section
uv run omnireach search "test" --limit 2  # no ✗ red rows for unavailable sources
```

---

## Self-review notes

- **Spec coverage**: §2 wechat/bilibili → tasks 3+4+5. §3 per-source timeout → task 2. §4 error classification → tasks 1+6. §5 verify script → task 7. §6 README line → task 7.
- **Type consistency**: `SourceError.category` introduced T1, used in T6 TTY render. `timeout_seconds: float | None` introduced T2, used in T2 dispatcher.
- **Ordering**: T1/T2 are foundation (contract.py / dispatcher / registry). T3/T4 add adapters. T5 wires them. T6 polishes UX. T7 dev tooling + docs. T8 ships.
- **Risk**: T6 footer test relies on the SourceError.category field added in T1 — confirmed ordering. T5 removes wechat/bilibili from `_setup_wip` path; if any other test still asserts wip behavior for them, T5 must adapt it (e.g. `test_sources_command_shows_wip_section` rewrite happens in T6).
