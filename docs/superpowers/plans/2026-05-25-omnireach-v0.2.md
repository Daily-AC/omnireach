# omnireach v0.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship omnireach v0.2 — add the conversational `omnireach setup <source>` wizard infrastructure, prove it out with the first one_step-tier source (Reddit via rdt-cli), and clear the two v0.1 follow-ups (switch HackerNews to Algolia Search API + warn on `--on` typos).

**Architecture:** Wizard is a thin orchestrator that reads `sources.yml` `deps.auto` (Agent-installable: pipx/npm) and `deps.manual` (user-only: OAuth, scan-to-login, install Chrome extension) per source spec. It uses `installer.py` (v0.1) for the auto parts, prints exact human instructions for the manual parts, then re-probes `adapter.is_ready()` as the final pass criterion. The Reddit adapter follows the same agent-reach subprocess template but its `is_ready()` ALSO checks for `rdt-cli` binary AND that an account is configured.

**Tech Stack:** Same as v0.1 — Python 3.10+, Click, pydantic v2, httpx, PyYAML, Rich, pytest+respx. No new deps.

**Spec reference:** `docs/superpowers/specs/2026-05-25-omnireach-design.md` (§8 wizard contract, §6 v1 sources, §12 roadmap)

**Base commit:** `5b32c68` (v0.1 squash-merge on main)
**Branch to create:** `feat/v0.2-wizard-and-reddit`

---

## File Structure (created/modified by this plan)

```
omnireach/
├── adapters/
│   ├── hackernews.py          # MODIFY (Task 1: Algolia switch)
│   └── reddit.py              # CREATE (Task 7)
├── router.py                   # MODIFY (Task 2: unknown_sources)
├── cli.py                      # MODIFY (Tasks 2 + 4: warning surface + setup_cmd register)
├── wizard.py                   # CREATE (Task 3: engine)
├── sources.yml                 # MODIFY (Task 6: add reddit entry)
└── commands/
    └── setup.py                # CREATE (Task 4: CLI subcommand)

tests/
├── adapters/
│   ├── test_hackernews.py     # MODIFY (Task 1: Algolia fixtures)
│   └── test_reddit.py         # CREATE (Task 7)
├── test_router.py              # MODIFY (Task 2: unknown_sources test)
├── test_wizard.py              # CREATE (Task 3)
├── test_cmd_setup.py           # CREATE (Task 4)
└── fixtures/
    └── hn_algolia_search.json # CREATE (Task 1)
```

---

## Task 0: Branch off main

**Files:** none (git operations only)

- [ ] **Step 1: From repo root, create the v0.2 branch off the post-merge main**

```bash
cd ~/Projects/omnireach && git checkout main && git pull origin main && git checkout -b feat/v0.2-wizard-and-reddit
```

Expected: on new branch `feat/v0.2-wizard-and-reddit`, HEAD = `5b32c68` (v0.1 squash commit).

- [ ] **Step 2: Verify baseline tests still pass**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 56 passed.

---

## Task 1: Switch HackerNews adapter to Algolia Search API

**Files:**
- Modify: `omnireach/adapters/hackernews.py`
- Modify: `tests/adapters/test_hackernews.py`
- Create: `tests/fixtures/hn_algolia_search.json`
- Delete: `tests/fixtures/hn_topstories.json`, `tests/fixtures/hn_item_1.json`, `tests/fixtures/hn_item_2.json`

Motivation: v0.1's HN adapter fetched 200 top stories then client-side filtered by title substring — 200 HTTP calls per query. Algolia's HN Search API (`https://hn.algolia.com/api/v1/search?query=<q>&tags=story&hitsPerPage=<n>`) returns ranked matches in one call.

- [ ] **Step 1: Create new Algolia fixture**

`tests/fixtures/hn_algolia_search.json`:

```json
{
  "hits": [
    {
      "objectID": "1",
      "title": "Claude 4.7 prompt caching benchmarks",
      "url": "https://example.com/post-1",
      "author": "alice",
      "created_at_i": 1748160000,
      "points": 250,
      "num_comments": 88
    },
    {
      "objectID": "2",
      "title": "Show HN: omnireach — search the whole internet from your agent",
      "url": "https://example.com/post-2",
      "author": "bob",
      "created_at_i": 1748170000,
      "points": 42,
      "num_comments": 6
    }
  ],
  "nbHits": 2,
  "page": 0,
  "hitsPerPage": 20
}
```

- [ ] **Step 2: Replace `tests/adapters/test_hackernews.py` entirely**

```python
from pathlib import Path

import httpx
import pytest
import respx

from omnireach.adapters.hackernews import HackerNewsAdapter


def _load(name: str) -> str:
    return (Path(__file__).parent.parent / "fixtures" / name).read_text()


@respx.mock
async def test_hn_search_returns_normalized_results():
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(200, text=_load("hn_algolia_search.json"))
    )

    a = HackerNewsAdapter()
    results = await a.search("claude", limit=5)

    assert len(results) == 2
    matched = next(r for r in results if "Claude 4.7" in r.title)
    assert matched.source == "hackernews"
    assert matched.adapter == "builtin"
    assert matched.url == "https://example.com/post-1"
    assert matched.author == "alice"
    assert matched.engagement is not None
    assert matched.engagement.likes == 250
    assert matched.engagement.comments == 88


@respx.mock
async def test_hn_search_passes_query_and_limit():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        return httpx.Response(200, text=_load("hn_algolia_search.json"))

    respx.get("https://hn.algolia.com/api/v1/search").mock(side_effect=handler)

    a = HackerNewsAdapter()
    await a.search("omnireach", limit=3)

    assert "query=omnireach" in captured["url"]
    assert "hitsPerPage=3" in captured["url"]
    assert "tags=story" in captured["url"]


@respx.mock
async def test_hn_search_falls_back_to_hn_url_when_url_missing():
    """Ask-HN posts have no external URL — must build news.ycombinator.com link."""
    fixture = """{"hits": [{"objectID": "42", "title": "Ask HN: foo", "url": null,
                 "author": "alice", "created_at_i": 1748160000, "points": 10, "num_comments": 2}]}"""
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(200, text=fixture)
    )

    a = HackerNewsAdapter()
    results = await a.search("ask", limit=5)
    assert results[0].url == "https://news.ycombinator.com/item?id=42"


async def test_hn_is_ready_does_not_call_network():
    a = HackerNewsAdapter()
    assert await a.is_ready() is True
```

- [ ] **Step 3: Run test — expect FAIL (adapter still uses old endpoints)**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/adapters/test_hackernews.py -x
```

Expected: 4 tests collected, 3 fail because the adapter still calls firebaseio.com (test_hn_is_ready will still pass).

- [ ] **Step 4: Replace `omnireach/adapters/hackernews.py` entirely**

```python
"""HackerNews adapter — talks directly to Algolia HN Search API, no upstream needed."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from omnireach.adapters.base import AdapterBase
from omnireach.contract import Engagement, SearchResult

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"


class HackerNewsAdapter(AdapterBase):
    name = "hackernews"
    requires: list[str] = []  # zero-config

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        params = {"query": query, "tags": "story", "hitsPerPage": limit}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(ALGOLIA_URL, params=params)
            data = resp.json()

        results: list[SearchResult] = []
        for hit in data.get("hits", [])[:limit]:
            object_id = hit.get("objectID") or ""
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
            created_i = hit.get("created_at_i") or 0
            ts = datetime.fromtimestamp(created_i, tz=timezone.utc).isoformat() if created_i else None
            points = hit.get("points") or 0
            results.append(
                SearchResult(
                    source="hackernews",
                    adapter="builtin",
                    title=hit.get("title") or "",
                    url=url,
                    content="",
                    author=hit.get("author"),
                    ts=ts,
                    score=min(1.0, points / 500.0),
                    engagement=Engagement(
                        likes=points,
                        comments=hit.get("num_comments"),
                    ),
                    raw=hit,
                )
            )
        return results
```

- [ ] **Step 5: Run tests — expect 4 passed**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/adapters/test_hackernews.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Delete stale fixtures**

```bash
cd ~/Projects/omnireach && git rm tests/fixtures/hn_topstories.json tests/fixtures/hn_item_1.json tests/fixtures/hn_item_2.json
```

- [ ] **Step 7: Run full suite to confirm no regression**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 56 passed (test count unchanged — we replaced 3 HN tests with 4, but the old test file had 3 tests too).

Wait — the new file has 4 tests, the old had 3. Expected: **57 passed**.

- [ ] **Step 8: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/adapters/hackernews.py tests/adapters/test_hackernews.py tests/fixtures/hn_algolia_search.json && git commit -m "perf(adapters): switch hackernews to Algolia Search API"
```

---

## Task 2: Surface unknown `--on` source as a warning

**Files:**
- Modify: `omnireach/router.py`
- Modify: `omnireach/cli.py`
- Modify: `tests/test_router.py`
- Modify: `tests/test_cli.py`

Motivation: v0.1 final review flagged that `omnireach search --on twiter "..."` (typo) silently drops to 0 results because the router filters unknown sources without telling anyone.

- [ ] **Step 1: Update `tests/test_router.py` — add unknown-source test**

Open `tests/test_router.py` and append:

```python
def test_unknown_explicit_source_recorded_in_route():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="x", explicit_sources=["hackernews", "twiter"]))
    assert route.source_ids == ["hackernews"]
    assert route.unknown_sources == ["twiter"]


def test_route_has_empty_unknown_sources_by_default():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="x"))
    assert route.unknown_sources == []
```

- [ ] **Step 2: Run — expect FAIL (Route lacks unknown_sources)**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_router.py -x
```

Expected: AttributeError or similar — `Route` has no `unknown_sources` attribute.

- [ ] **Step 3: Update `omnireach/router.py`**

Replace the contents entirely with:

```python
"""Router — picks which sources to fan out to for a given query."""

from __future__ import annotations

from dataclasses import dataclass, field

from omnireach.registry import Registry

MAX_SOURCES = 5


@dataclass
class RouteRequest:
    query: str
    explicit_sources: list[str] | None = None
    mode: str = "auto"


@dataclass
class Route:
    source_ids: list[str]
    rationale: str
    unknown_sources: list[str] = field(default_factory=list)


class Router:
    def __init__(self, registry: Registry) -> None:
        self.registry = registry

    def plan(self, req: RouteRequest) -> Route:
        if req.explicit_sources:
            valid = [s.id for s in self.registry.sources]
            chosen = [s for s in req.explicit_sources if s in valid]
            unknown = [s for s in req.explicit_sources if s not in valid]
            return Route(source_ids=chosen, rationale="explicit --on", unknown_sources=unknown)

        if req.mode == "quick":
            return Route(source_ids=["web", "hackernews"], rationale="mode=quick")

        if req.mode == "deep":
            all_ready = [s.id for s in self.registry.sources if s.tier == "ready"]
            return Route(source_ids=all_ready[:MAX_SOURCES], rationale="mode=deep")

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

- [ ] **Step 4: Run router tests — expect PASS**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_router.py -v
```

Expected: 7 passed (5 original + 2 new).

- [ ] **Step 5: Update `omnireach/cli.py` `search_cmd` to surface warnings**

Open `omnireach/cli.py`. Find the `search_cmd` function. After the line `route = router.plan(...)`, insert this block (before the adapter-loading loop):

```python
    for unknown in route.unknown_sources:
        click.echo(f"warning: 未知源 '{unknown}' — 跳过 (用 `omnireach sources` 查看可用源)", err=True)
```

The complete `search_cmd` after this edit should look like:

```python
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

    for unknown in route.unknown_sources:
        click.echo(f"warning: 未知源 '{unknown}' — 跳过 (用 `omnireach sources` 查看可用源)", err=True)

    adapters = {}
    for sid in route.source_ids:
        try:
            spec = reg.get(sid)
            adapters[sid] = spec.load_adapter_class()()
        except Exception as e:  # noqa: BLE001
            click.echo(f"skip {sid}: {e}", err=True)

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
```

- [ ] **Step 6: Add a CLI test for the warning. Append to `tests/test_cli.py`:**

```python
def test_cli_search_warns_on_unknown_on_source(monkeypatch):
    """--on with a typo should print a warning to stderr (and still run the valid sources)."""
    import omnireach.adapters.hackernews as hn

    async def fake_search(self, query, *, limit=10):
        from omnireach.contract import SearchResult
        return [
            SearchResult(
                source="hackernews",
                adapter="builtin",
                title="ok",
                url="https://e.x/1",
                ts="2026-05-25T12:00:00Z",
                score=0.5,
            )
        ]

    monkeypatch.setattr(hn.HackerNewsAdapter, "search", fake_search)

    runner = CliRunner()
    res = runner.invoke(main, ["search", "--on", "hackernews,twiter", "--json", "x"])
    assert res.exit_code == 0, res.output
    assert "未知源" in res.stderr or "未知源" in res.output
    assert "twiter" in res.stderr or "twiter" in res.output
```

- [ ] **Step 7: Run CLI tests — expect PASS**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_cli.py -v
```

Expected: 4 passed (3 original + 1 new).

- [ ] **Step 8: Run full suite**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 60 passed (57 from Task 1 + 2 router + 1 cli).

- [ ] **Step 9: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/router.py omnireach/cli.py tests/test_router.py tests/test_cli.py && git commit -m "feat(router,cli): warn on unknown --on source instead of silent drop"
```

---

## Task 3: Wizard core engine

**Files:**
- Create: `omnireach/wizard.py`
- Create: `tests/test_wizard.py`

This is the heart of v0.2. The wizard reads a source's `deps.auto` (Agent-installable) and `deps.manual` (user-only), runs Agent steps automatically via `installer.py`, prints exact instructions for manual steps, then re-probes `adapter.is_ready()` as the pass criterion.

- [ ] **Step 1: Write `tests/test_wizard.py`**

```python
import pytest

from omnireach.adapters.base import AdapterBase
from omnireach.contract import SearchResult
from omnireach.installer import InstallError
from omnireach.registry import Dep, SourceSpec
from omnireach.wizard import (
    SetupReport,
    StepKind,
    StepStatus,
    WizardStep,
    run_setup,
)


class _StubAdapter(AdapterBase):
    name = "stub"

    def __init__(self, ready: bool = True) -> None:
        self._ready = ready

    async def is_ready(self) -> bool:
        return self._ready

    async def search(self, query, *, limit=10):
        return []


def _spec(auto: list[Dep] | None = None, manual: list[Dep] | None = None) -> SourceSpec:
    return SourceSpec(
        id="stub",
        tier="one_step",
        adapter="tests.test_wizard._StubAdapter",
        description="stub",
        deps_auto=auto or [],
        deps_manual=manual or [],
    )


async def test_setup_skips_when_adapter_already_ready(monkeypatch):
    """If is_ready() already True, wizard returns SKIPPED for all steps."""
    spec = _spec(auto=[Dep(kind="pipx", name="agent-reach")])
    report = await run_setup(
        spec,
        adapter=_StubAdapter(ready=True),
        confirm=lambda msg: True,
        run_install=lambda kind, name: None,
        prompt_user_step=lambda step: None,
    )
    assert report.already_ready is True
    assert all(s.status == StepStatus.SKIPPED for s in report.steps)


async def test_setup_runs_auto_install_then_manual_then_verifies(monkeypatch):
    """Happy path: pipx install runs, manual step prompts user, final is_ready() True."""
    installs: list[tuple[str, str]] = []

    spec = _spec(
        auto=[Dep(kind="pipx", name="agent-reach"), Dep(kind="npm", name="rdt-cli")],
        manual=[Dep(step="跑 `rdt login`")],
    )

    # adapter not ready initially, becomes ready after install
    adapter = _StubAdapter(ready=False)

    def run_install(kind: str, name: str) -> None:
        installs.append((kind, name))
        adapter._ready = True  # simulate post-install readiness

    prompts: list[str] = []

    def prompt_user_step(step: Dep) -> None:
        prompts.append(step.step)

    report = await run_setup(
        spec,
        adapter=adapter,
        confirm=lambda msg: True,
        run_install=run_install,
        prompt_user_step=prompt_user_step,
    )

    assert installs == [("pipx", "agent-reach"), ("npm", "rdt-cli")]
    assert prompts == ["跑 `rdt login`"]
    assert report.success is True
    assert report.already_ready is False
    assert [s.kind for s in report.steps] == [StepKind.AUTO, StepKind.AUTO, StepKind.MANUAL, StepKind.VERIFY]
    assert all(s.status == StepStatus.OK for s in report.steps)


async def test_setup_aborts_when_user_declines_confirmation():
    spec = _spec(auto=[Dep(kind="pipx", name="agent-reach")])
    report = await run_setup(
        spec,
        adapter=_StubAdapter(ready=False),
        confirm=lambda msg: False,  # user declines
        run_install=lambda kind, name: None,
        prompt_user_step=lambda step: None,
    )
    assert report.success is False
    assert report.aborted is True


async def test_setup_marks_failed_install_step(monkeypatch):
    spec = _spec(auto=[Dep(kind="pipx", name="agent-reach")])

    def run_install(kind: str, name: str) -> None:
        raise InstallError(name, "pipx blew up", hint="install pipx first")

    report = await run_setup(
        spec,
        adapter=_StubAdapter(ready=False),
        confirm=lambda msg: True,
        run_install=run_install,
        prompt_user_step=lambda step: None,
    )
    assert report.success is False
    assert any(s.kind == StepKind.AUTO and s.status == StepStatus.FAILED for s in report.steps)
    failed = next(s for s in report.steps if s.status == StepStatus.FAILED)
    assert "pipx blew up" in (failed.detail or "")


async def test_setup_verify_fails_when_adapter_still_not_ready():
    spec = _spec(auto=[Dep(kind="pipx", name="agent-reach")])
    # adapter stays not-ready even after install
    adapter = _StubAdapter(ready=False)

    report = await run_setup(
        spec,
        adapter=adapter,
        confirm=lambda msg: True,
        run_install=lambda kind, name: None,
        prompt_user_step=lambda step: None,
    )
    assert report.success is False
    verify_step = next(s for s in report.steps if s.kind == StepKind.VERIFY)
    assert verify_step.status == StepStatus.FAILED
```

- [ ] **Step 2: Run — expect FAIL (wizard module missing)**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_wizard.py -x
```

Expected: ImportError on `omnireach.wizard`.

- [ ] **Step 3: Implement `omnireach/wizard.py`**

```python
"""Wizard — drive a source's setup flow.

The wizard is dependency-injected: tests pass stubs for `confirm`,
`run_install`, and `prompt_user_step`. The CLI subcommand (Task 4)
will wire them to Click prompts + installer.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable

from omnireach.adapters.base import AdapterBase
from omnireach.installer import InstallError
from omnireach.registry import Dep, SourceSpec


class StepKind(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"
    VERIFY = "verify"


class StepStatus(str, Enum):
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WizardStep:
    kind: StepKind
    label: str
    status: StepStatus
    detail: str | None = None


@dataclass
class SetupReport:
    source_id: str
    steps: list[WizardStep] = field(default_factory=list)
    already_ready: bool = False
    aborted: bool = False

    @property
    def success(self) -> bool:
        if self.aborted:
            return False
        if not self.steps:
            return False
        return all(s.status in (StepStatus.OK, StepStatus.SKIPPED) for s in self.steps)


ConfirmFn = Callable[[str], bool]
InstallFn = Callable[[str, str], None]
PromptFn = Callable[[Dep], None]


async def run_setup(
    spec: SourceSpec,
    *,
    adapter: AdapterBase,
    confirm: ConfirmFn,
    run_install: InstallFn,
    prompt_user_step: PromptFn,
) -> SetupReport:
    """Drive a source through its setup steps. Returns a structured report.

    Pre-check: if adapter.is_ready() is already True, return immediately with
    all steps marked SKIPPED.

    Otherwise:
      1. Confirm overall flow with the user.
      2. For each auto dep, call run_install(kind, name); on InstallError, mark step FAILED and stop.
      3. For each manual dep, call prompt_user_step(dep) (which is expected to block until user signals done).
      4. Re-probe adapter.is_ready(). VERIFY step is OK iff ready, FAILED otherwise.
    """
    report = SetupReport(source_id=spec.id)

    if await adapter.is_ready():
        report.already_ready = True
        for dep in spec.deps_auto:
            report.steps.append(WizardStep(StepKind.AUTO, f"{dep.kind} install {dep.name}", StepStatus.SKIPPED))
        for dep in spec.deps_manual:
            report.steps.append(WizardStep(StepKind.MANUAL, dep.step, StepStatus.SKIPPED))
        report.steps.append(WizardStep(StepKind.VERIFY, "is_ready()", StepStatus.SKIPPED))
        return report

    if not confirm(f"开始配置 '{spec.id}'?"):
        report.aborted = True
        return report

    for dep in spec.deps_auto:
        label = f"{dep.kind} install {dep.name}"
        try:
            run_install(dep.kind, dep.name)
            report.steps.append(WizardStep(StepKind.AUTO, label, StepStatus.OK))
        except InstallError as e:
            report.steps.append(
                WizardStep(StepKind.AUTO, label, StepStatus.FAILED, detail=str(e))
            )
            return report

    for dep in spec.deps_manual:
        prompt_user_step(dep)
        report.steps.append(WizardStep(StepKind.MANUAL, dep.step, StepStatus.OK))

    ready = await adapter.is_ready()
    report.steps.append(
        WizardStep(
            StepKind.VERIFY,
            "is_ready()",
            StepStatus.OK if ready else StepStatus.FAILED,
            detail=None if ready else "adapter still not ready after setup",
        )
    )
    return report
```

- [ ] **Step 4: Run wizard tests — expect 5 passed**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_wizard.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Full suite check**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 65 passed (60 from Tasks 1-2 + 5 new).

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/wizard.py tests/test_wizard.py && git commit -m "feat(wizard): dependency-injected setup engine"
```

---

## Task 4: `setup <source>` CLI subcommand

**Files:**
- Create: `omnireach/commands/setup.py`
- Modify: `omnireach/cli.py` (register `setup_cmd`)
- Create: `tests/test_cmd_setup.py`

- [ ] **Step 1: Write `tests/test_cmd_setup.py`**

```python
from click.testing import CliRunner

from omnireach.cli import main


def test_setup_requires_known_source():
    runner = CliRunner()
    res = runner.invoke(main, ["setup", "nope"])
    assert res.exit_code != 0
    assert "未知" in res.output or "unknown" in res.output.lower()


def test_setup_runs_wizard_on_known_source(monkeypatch):
    """`setup hackernews --yes` should succeed immediately since HN is_ready=True."""
    runner = CliRunner()
    res = runner.invoke(main, ["setup", "hackernews", "--yes"])
    assert res.exit_code == 0, res.output
    assert "已就绪" in res.output or "ready" in res.output.lower()


def test_setup_reports_failure(monkeypatch):
    """When the wizard reports failure (e.g. install error), CLI exits non-zero."""
    from omnireach import wizard as wiz_mod
    from omnireach.wizard import SetupReport, StepKind, StepStatus, WizardStep

    async def fake_run_setup(*args, **kwargs):
        return SetupReport(
            source_id="reddit",
            steps=[
                WizardStep(
                    StepKind.AUTO,
                    "npm install rdt-cli",
                    StepStatus.FAILED,
                    detail="install rdt-cli failed: network",
                )
            ],
        )

    monkeypatch.setattr(wiz_mod, "run_setup", fake_run_setup)

    runner = CliRunner()
    res = runner.invoke(main, ["setup", "hackernews", "--yes"])
    assert res.exit_code == 1
    assert "失败" in res.output or "failed" in res.output.lower()
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_cmd_setup.py -x
```

Expected: command not found.

- [ ] **Step 3: Implement `omnireach/commands/setup.py`**

```python
"""omnireach setup <source> — conversational setup wizard."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console

from omnireach import installer, wizard
from omnireach.registry import Dep, load_registry
from omnireach.wizard import StepKind, StepStatus

console = Console()


def _confirm_factory(yes: bool):
    def confirm(msg: str) -> bool:
        if yes:
            return True
        return click.confirm(msg, default=True)

    return confirm


def _run_install(kind: str, name: str) -> None:
    if kind == "pipx":
        installer.install_pipx_package(name)
    elif kind == "npm":
        installer.install_npm_global(name)
    else:
        raise installer.InstallError(name, f"unknown install kind '{kind}'")


def _prompt_user_step_factory(yes: bool):
    def prompt(step: Dep) -> None:
        console.print(f"[bold yellow]👤 你需要做的:[/bold yellow] {step.step}")
        if not yes:
            click.prompt("做完按回车继续", default="", show_default=False)

    return prompt


@click.command("setup")
@click.argument("source_id")
@click.option("--yes", "-y", is_flag=True, help="跳过所有确认 (CI / 自动化)")
def setup_cmd(source_id: str, yes: bool) -> None:
    """配置一个源 (装上游工具 + 引导用户登录)."""
    reg = load_registry()
    try:
        spec = reg.get(source_id)
    except KeyError:
        click.echo(f"未知源 '{source_id}'. 可用源: 跑 `omnireach sources`", err=True)
        raise SystemExit(2)

    adapter = spec.load_adapter_class()()
    report = asyncio.run(
        wizard.run_setup(
            spec,
            adapter=adapter,
            confirm=_confirm_factory(yes),
            run_install=_run_install,
            prompt_user_step=_prompt_user_step_factory(yes),
        )
    )

    if report.already_ready:
        console.print(f"[green]✅ {source_id} 已就绪, 无需配置[/green]")
        return

    if report.aborted:
        console.print(f"[yellow]取消配置 {source_id}[/yellow]")
        raise SystemExit(1)

    icon = {StepStatus.OK: "✅", StepStatus.FAILED: "❌", StepStatus.SKIPPED: "⏭️"}
    for step in report.steps:
        kind_label = {StepKind.AUTO: "[Agent]", StepKind.MANUAL: "[你]", StepKind.VERIFY: "[验证]"}[step.kind]
        line = f"{icon[step.status]} {kind_label} {step.label}"
        if step.detail:
            line += f" — {step.detail}"
        console.print(line)

    if report.success:
        console.print(f"[green]✅ {source_id} 配置完成[/green]")
    else:
        console.print(f"[red]❌ {source_id} 配置失败[/red]")
        raise SystemExit(1)
```

- [ ] **Step 4: Register `setup_cmd` in `omnireach/cli.py`**

Add to imports near the top of `omnireach/cli.py`:

```python
from omnireach.commands.setup import setup_cmd
```

Add after the existing `main.add_command(...)` calls (sources_cmd should be last):

```python
main.add_command(setup_cmd)
```

- [ ] **Step 5: Run setup tests**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_cmd_setup.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Smoke test in shell**

```bash
cd ~/Projects/omnireach && omnireach setup hackernews
```

Expected: prints "✅ hackernews 已就绪, 无需配置" and exits 0.

- [ ] **Step 7: Full suite**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 68 passed (65 + 3 setup).

- [ ] **Step 8: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/commands/setup.py omnireach/cli.py tests/test_cmd_setup.py && git commit -m "feat(cli): setup subcommand drives wizard for source onboarding"
```

---

## Task 5: Add `reddit` entry to sources.yml

**Files:**
- Modify: `omnireach/sources.yml`
- Modify: `tests/test_registry.py` (update count assertion 7 → 8)

- [ ] **Step 1: Update `tests/test_registry.py`**

Find the assertion `assert len(reg.sources) == 7` in `test_load_registry_returns_all_sources` and change it to `== 8`. Also add `"reddit" in ids` assertion.

The updated test function should look like:

```python
def test_load_registry_returns_all_sources():
    reg = load_registry()
    ids = [s.id for s in reg.sources]
    assert "hackernews" in ids
    assert "web" in ids
    assert "wechat" in ids
    assert "bilibili" in ids
    assert "reddit" in ids
    assert len(reg.sources) == 8
```

- [ ] **Step 2: Run — expect FAIL (no reddit yet)**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_registry.py -x
```

Expected: AssertionError on reddit presence or count.

- [ ] **Step 3: Append `reddit` entry to `omnireach/sources.yml`**

Add this block after the `bilibili` entry (at end of file):

```yaml

- id: reddit
  tier: one_step
  adapter: omnireach.adapters.reddit.RedditAdapter
  description: Reddit 帖子 + 评论搜索 (需要 rdt-cli 登录)
  query_hints: [reddit, "r/", subreddit]
  default_in_auto: true
  deps:
    auto:
      - { kind: pipx, name: agent-reach }
      - { kind: npm, name: rdt-cli }
    manual:
      - { step: "在浏览器完成 Reddit OAuth — 运行 `rdt login` 并按提示授权" }
```

- [ ] **Step 4: Run registry tests — expect PASS**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_registry.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Run sources subcommand test (the count check)**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_cmd_sources.py -v
```

Expected: 2 passed (the existing test loops `["hackernews", ...]`; it doesn't enforce an exact count). If it fails because the test was strict, update it to include reddit.

- [ ] **Step 6: Run doctor test (will fail because reddit adapter class doesn't exist yet)**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_doctor.py -v
```

Expected: 2 passed. (Doctor catches the `ModuleNotFoundError` from `omnireach.adapters.reddit` and reports it as `ok=False` — same pattern as during v0.1 dev. Test asserts `"hackernews" in ids` and `hn.ok is True`, both still true.)

- [ ] **Step 7: Full suite**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 68 passed (unchanged — same number of tests, just one updated assertion).

- [ ] **Step 8: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/sources.yml tests/test_registry.py && git commit -m "feat(registry): add reddit entry (one_step tier)"
```

---

## Task 6: Reddit adapter via agent-reach + rdt-cli

**Files:**
- Create: `omnireach/adapters/reddit.py`
- Create: `tests/adapters/test_reddit.py`

This adapter follows the same agent-reach subprocess pattern as web/youtube/github/etc. BUT its `is_ready()` is stricter — it must verify (1) `agent-reach` binary exists, (2) `rdt-cli` binary exists, AND (3) `rdt-cli` has at least one configured account.

The third check is done by running `rdt-cli accounts list` and looking for non-empty output. If `rdt-cli` doesn't have an `accounts list` subcommand, we fall back to running `rdt-cli` with `--help` (just checks the binary works) and trust the search call to fail with a clear error on missing auth.

For this v0.2 implementation we keep it simple: `is_ready()` checks both binaries exist; if account is missing, the search call will fail with whatever stderr rdt-cli emits, and our `AdapterUnavailable` carries that stderr verbatim. That's good UX — the user sees the real error.

- [ ] **Step 1: Write `tests/adapters/test_reddit.py`**

```python
import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.reddit import RedditAdapter


async def test_reddit_search_parses_agent_reach_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "How does Claude 4.7 prompt caching actually work?",
                "url": "https://reddit.com/r/ClaudeAI/comments/abc",
                "subreddit": "ClaudeAI",
                "author": "u/alice",
                "selftext": "I've been testing...",
                "score": 245,
                "num_comments": 67,
                "created_utc": "2026-05-20T12:00:00Z",
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.reddit.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(
        "omnireach.adapters.reddit.shutil.which",
        lambda n: "/usr/bin/" + n,  # both agent-reach and rdt-cli exist
    )

    out = await RedditAdapter().search("claude", limit=3)
    assert len(out) == 1
    assert out[0].source == "reddit"
    assert out[0].author == "u/alice"
    assert out[0].engagement.likes == 245
    assert out[0].engagement.comments == 67
    assert "ClaudeAI" in out[0].raw.get("subreddit", "")


async def test_reddit_missing_agent_reach(monkeypatch):
    monkeypatch.setattr(
        "omnireach.adapters.reddit.shutil.which",
        lambda n: None if n == "agent-reach" else "/usr/bin/" + n,
    )
    with pytest.raises(AdapterUnavailable) as exc:
        await RedditAdapter().search("x")
    assert "agent-reach" in str(exc.value)


async def test_reddit_missing_rdt_cli(monkeypatch):
    monkeypatch.setattr(
        "omnireach.adapters.reddit.shutil.which",
        lambda n: None if n == "rdt-cli" else "/usr/bin/" + n,
    )
    with pytest.raises(AdapterUnavailable) as exc:
        await RedditAdapter().search("x")
    assert "rdt-cli" in str(exc.value)


async def test_reddit_is_ready_requires_both_binaries(monkeypatch):
    monkeypatch.setattr(
        "omnireach.adapters.reddit.shutil.which",
        lambda n: "/usr/bin/" + n,
    )
    assert await RedditAdapter().is_ready() is True

    monkeypatch.setattr(
        "omnireach.adapters.reddit.shutil.which",
        lambda n: None if n == "rdt-cli" else "/usr/bin/" + n,
    )
    assert await RedditAdapter().is_ready() is False
```

- [ ] **Step 2: Run — expect FAIL (module missing)**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/adapters/test_reddit.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/adapters/reddit.py`**

```python
"""Reddit adapter — shells out to agent-reach (which uses rdt-cli under the hood).

Unlike the other agent-reach adapters, Reddit requires BOTH `agent-reach` AND
`rdt-cli` binaries on PATH, since agent-reach delegates Reddit calls to rdt-cli.
"""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


class RedditAdapter(AdapterBase):
    name = "reddit"
    requires = ["agent-reach", "rdt-cli"]

    async def is_ready(self) -> bool:
        return all(shutil.which(b) is not None for b in self.requires)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("agent-reach"):
            raise AdapterUnavailable(
                "reddit", "agent-reach not installed", hint="omnireach setup reddit"
            )
        if not shutil.which("rdt-cli"):
            raise AdapterUnavailable(
                "reddit", "rdt-cli not installed", hint="omnireach setup reddit"
            )

        proc = await asyncio.create_subprocess_exec(
            "agent-reach", "reddit", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("reddit", err.decode().strip() or "agent-reach reddit search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("reddit", f"agent-reach returned non-JSON: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    source="reddit",
                    adapter="agent-reach",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("selftext", "") or item.get("body", ""),
                    author=item.get("author"),
                    ts=item.get("created_utc") or item.get("created_at"),
                    score=0.5,
                    engagement=Engagement(
                        likes=item.get("score"),
                        comments=item.get("num_comments"),
                    ),
                    raw=item,
                )
            )
        return results
```

- [ ] **Step 4: Run reddit tests — expect 4 passed**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/adapters/test_reddit.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Verify `omnireach sources` lists reddit correctly**

```bash
cd ~/Projects/omnireach && omnireach sources
```

Expected: prints `🟡 one_step (1)` table with `reddit` row.

- [ ] **Step 6: Verify `omnireach doctor`**

```bash
cd ~/Projects/omnireach && omnireach doctor
```

Expected: reddit shows ❌ with detail "not ready" (since neither binary is installed locally) — this is the expected state in dev.

- [ ] **Step 7: Full suite**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 72 passed (68 + 4 reddit).

- [ ] **Step 8: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/adapters/reddit.py tests/adapters/test_reddit.py && git commit -m "feat(adapters): reddit via agent-reach + rdt-cli"
```

---

## Task 7: Update README + tag v0.2.0-alpha

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current `README.md`** (it's the v0.1 version)

```bash
cd ~/Projects/omnireach && cat README.md
```

- [ ] **Step 2: Update the "v0.1 支持的源" section and add v0.2 section**

Find the section:

```markdown
## v0.1 支持的源

✅ **零配置 (7 个)**: `web` · `hackernews` · `youtube` · `github` · `rss` · `wechat` (微信公众号) · `bilibili` (B 站)

🟡 / 🔴 计划中 (v0.2+): `reddit` · `twitter` · `xiaohongshu` (小红书)
```

Replace with:

```markdown
## 支持的源

✅ **零配置 (7 个)**: `web` · `hackernews` · `youtube` · `github` · `rss` · `wechat` (微信公众号) · `bilibili` (B 站)

🟡 **一步配置 (1 个, v0.2 新增)**: `reddit` — 跑 `omnireach setup reddit`, Agent 自动装 rdt-cli, 你完成 OAuth

🔴 计划中 (v0.3+): `twitter` · `xiaohongshu` (小红书)
```

Also add to the "命令" table (between `sources` and `doctor`):

```markdown
| `omnireach setup <source>` | 引导式配置一个 🟡 / 🔴 源 (Agent 装上游 + 你完成认证) |
```

- [ ] **Step 3: Final full suite**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 72 passed.

- [ ] **Step 4: Commit README**

```bash
cd ~/Projects/omnireach && git add README.md && git commit -m "docs: README for v0.2 (reddit + setup subcommand)"
```

- [ ] **Step 5: Tag v0.2.0-alpha**

```bash
cd ~/Projects/omnireach && git tag -a v0.2.0-alpha -m "omnireach v0.2.0-alpha — wizard + reddit + HN Algolia + --on warning"
```

- [ ] **Step 6: Final branch summary**

```bash
cd ~/Projects/omnireach && git log --oneline main..feat/v0.2-wizard-and-reddit && git tag -l
```

Expected: 7 commits + tag `v0.2.0-alpha`.

---

## Self-review notes

- **Spec coverage check**: §12 v0.2 row says "解锁 reddit / 微信公众号 / B站 + 引导式 wizard 完整化". 微信公众号 and B站 already shipped in v0.1 (covered). Reddit = Task 6. Wizard = Tasks 3+4. §8 wizard "Agent 能做的 vs 用户做的" split implemented via `deps_auto` (run_install) vs `deps_manual` (prompt_user_step). §10 "绝不静默" — Task 2 covers the `--on` silent drop bug. v0.1 final-review HN concern — Task 1.

- **Type consistency check**: `SetupReport`, `WizardStep`, `StepKind`, `StepStatus` all defined in Task 3 and re-imported in Tasks 4. `Dep` from `registry.py` (v0.1) flows through wizard injection. `Route.unknown_sources` added in Task 2 and consumed in CLI (same task).

- **No placeholders**: every step has actual content. Tasks 1, 2, 3, 4 have complete tests. Tasks 5, 6, 7 have full file contents.

- **Test count progression**: v0.1 baseline 56 → Task 1 (+1 = 57) → Task 2 (+3 = 60) → Task 3 (+5 = 65) → Task 4 (+3 = 68) → Task 5 (no count change = 68) → Task 6 (+4 = 72) → Task 7 (no change = 72).
