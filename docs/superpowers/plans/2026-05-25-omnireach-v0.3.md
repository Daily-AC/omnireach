# omnireach v0.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship omnireach v0.3 — add the two 🔴 heavy-tier sources (Twitter + 小红书) via OpenCLI's logged-in Chrome bridge, plus close the wizard's spec gap by adding the `verify` command loop that auto-confirms each manual step before marking it complete.

**Architecture:** Wizard gains a fourth DI callable, `run_verify(cmd: str) -> tuple[int, str]` (returns exit code + combined output). After `prompt_user_step(dep)` returns, if `dep.verify` is non-empty, the wizard runs it; non-zero exit → step FAILED with the captured stderr/stdout as `detail`. Twitter and 小红书 adapters subprocess-call `opencli <site> search --json` and require BOTH `opencli` binary AND a passing `opencli doctor` (which itself checks the Chrome bridge extension + at least one connected profile). Same setup steps for both — install OpenCLI npm pkg, install Chrome extension (manual + verify via `opencli doctor`), then per-site login (manual + verify via `opencli <site> state` if available; else by attempting a 1-result search).

**Tech Stack:** Same as v0.2 — no new deps. We rely on `opencli` being on PATH (installed via `installer.install_npm_global("@jackwener/opencli")` in the wizard's auto step).

**Spec reference:** `docs/superpowers/specs/2026-05-25-omnireach-design.md` (§6 source list, §8 wizard contract, §12 roadmap v0.3 row).

**Base commit:** `dd4ce96` (v0.2 squash on main).
**Branch to create:** `feat/v0.3-twitter-xiaohongshu`.

---

## File Structure (created/modified by this plan)

```
omnireach/
├── adapters/
│   ├── twitter.py              # CREATE (Task 3)
│   └── xiaohongshu.py          # CREATE (Task 4)
├── commands/
│   └── setup.py                # MODIFY (Task 1: wire run_verify)
├── installer.py                # MODIFY (Task 1: add install_npm_global path verifier helper)
├── wizard.py                   # MODIFY (Task 1: verify loop)
└── sources.yml                 # MODIFY (Task 5: add twitter + xiaohongshu)

tests/
├── adapters/
│   ├── test_twitter.py         # CREATE (Task 3)
│   └── test_xiaohongshu.py     # CREATE (Task 4)
├── test_wizard.py              # MODIFY (Task 1: verify tests)
└── test_cmd_setup.py           # MODIFY (Task 1: end-to-end verify test)
```

Renames intentionally avoided — every change is additive except for `wizard.py` which gains a new arg to `run_setup()` (with a no-op default to preserve compatibility with the Task 4 setup.py call site).

---

## Task 0: Branch off main

**Files:** none (git operations only).

- [ ] **Step 1: From repo root, pull latest main and create the v0.3 branch**

```bash
cd ~/Projects/omnireach && git checkout main && git pull origin main && git checkout -b feat/v0.3-twitter-xiaohongshu
```

Expected: on new branch `feat/v0.3-twitter-xiaohongshu`, HEAD = `dd4ce96` (v0.2 squash).

- [ ] **Step 2: Verify baseline tests still pass**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 72 passed.

---

## Task 1: Wizard `verify` loop

**Files:**
- Modify: `omnireach/wizard.py`
- Modify: `omnireach/commands/setup.py`
- Modify: `tests/test_wizard.py`

Today the wizard prints the manual step, waits for the user, then marks it OK regardless of whether the user actually finished. With `verify`, every manual `Dep` can carry a shell command (e.g., `opencli doctor`) that auto-confirms completion. Non-zero exit → step FAILED, captured stderr/stdout shown in the report.

### Implementation outline

- Add a new DI callable `RunVerifyFn = Callable[[str], tuple[int, str]]` that takes a shell command and returns `(exit_code, combined_output)`. In tests it's a stub; in `setup.py` it's a `subprocess.run(..., shell=True, capture_output=True, text=True)` call.
- After `prompt_user_step(dep)` returns, if `dep.verify` is non-empty, run it. On non-zero exit, mark the step FAILED with the output as `detail` and **early-return** (don't continue to subsequent manual steps or the final verify). This matches the existing early-return-on-install-failure pattern.

### Steps

- [ ] **Step 1: Update `tests/test_wizard.py` — add two new tests**

Append at the end of `tests/test_wizard.py`:

```python
async def test_setup_runs_verify_after_manual_step_when_provided():
    """When dep.verify is set, wizard runs it after the manual step. exit 0 → OK."""
    spec = _spec(
        manual=[Dep(step="login somewhere", verify="echo done")],
    )
    adapter = _StubAdapter(ready=False)

    def post_manual_make_ready():
        adapter._ready = True

    verifies: list[str] = []

    def run_verify(cmd: str) -> tuple[int, str]:
        verifies.append(cmd)
        post_manual_make_ready()
        return (0, "done\n")

    report = await run_setup(
        spec,
        adapter=adapter,
        confirm=lambda msg: True,
        run_install=lambda kind, name: None,
        prompt_user_step=lambda step: None,
        run_verify=run_verify,
    )

    assert verifies == ["echo done"]
    assert report.success is True
    manual_step = next(s for s in report.steps if s.kind == StepKind.MANUAL)
    assert manual_step.status == StepStatus.OK


async def test_setup_marks_manual_failed_when_verify_fails():
    """When verify exits non-zero, the manual step is FAILED and wizard early-returns."""
    spec = _spec(
        manual=[
            Dep(step="step A", verify="exit 1"),
            Dep(step="step B"),  # should not be reached
        ],
    )
    adapter = _StubAdapter(ready=False)

    prompts_seen: list[str] = []

    def prompt_user_step(dep: Dep) -> None:
        prompts_seen.append(dep.step)

    def run_verify(cmd: str) -> tuple[int, str]:
        return (1, "boom: not logged in")

    report = await run_setup(
        spec,
        adapter=adapter,
        confirm=lambda msg: True,
        run_install=lambda kind, name: None,
        prompt_user_step=prompt_user_step,
        run_verify=run_verify,
    )

    assert prompts_seen == ["step A"]  # step B never prompted
    assert report.success is False
    failed = next(s for s in report.steps if s.status == StepStatus.FAILED)
    assert failed.kind == StepKind.MANUAL
    assert "boom" in (failed.detail or "")
    # No VERIFY step appended (final readiness probe skipped on early-return)
    assert not any(s.kind == StepKind.VERIFY for s in report.steps)


async def test_setup_skips_verify_when_dep_has_no_verify():
    """Manual deps without a verify field continue to mark OK without invoking run_verify."""
    spec = _spec(manual=[Dep(step="just do it")])
    adapter = _StubAdapter(ready=True)  # final probe wins anyway
    # adapter starts ready=True so already_ready short-circuits this case;
    # use ready=False to actually exercise the manual loop:
    adapter._ready = False

    def make_ready_after_prompt(dep):
        adapter._ready = True

    def boom_verify(cmd: str) -> tuple[int, str]:
        raise AssertionError("run_verify must NOT be called when dep.verify is empty")

    report = await run_setup(
        spec,
        adapter=adapter,
        confirm=lambda msg: True,
        run_install=lambda kind, name: None,
        prompt_user_step=make_ready_after_prompt,
        run_verify=boom_verify,
    )

    assert report.success is True
    manual_step = next(s for s in report.steps if s.kind == StepKind.MANUAL)
    assert manual_step.status == StepStatus.OK
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_wizard.py -x
```

Expected: TypeError — `run_setup()` got unexpected keyword argument `run_verify`.

- [ ] **Step 3: Modify `omnireach/wizard.py` — replace the whole file**

```python
"""Wizard — drive a source's setup flow.

The wizard is dependency-injected: tests pass stubs for `confirm`,
`run_install`, `prompt_user_step`, and `run_verify`. The CLI subcommand
wires them to Click prompts + installer.py + subprocess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

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
RunVerifyFn = Callable[[str], tuple[int, str]]


def _noop_verify(cmd: str) -> tuple[int, str]:  # pragma: no cover - default fallback
    return (0, "")


async def run_setup(
    spec: SourceSpec,
    *,
    adapter: AdapterBase,
    confirm: ConfirmFn,
    run_install: InstallFn,
    prompt_user_step: PromptFn,
    run_verify: RunVerifyFn = _noop_verify,
) -> SetupReport:
    """Drive a source through its setup steps. Returns a structured report.

    Pre-check: if adapter.is_ready() is already True, return immediately with
    all steps marked SKIPPED.

    Otherwise:
      1. Confirm overall flow with the user.
      2. For each auto dep, call run_install(kind, name); on InstallError, mark step FAILED and stop.
      3. For each manual dep, call prompt_user_step(dep). If dep.verify is set,
         run_verify(dep.verify) — exit 0 = MANUAL OK, non-zero = MANUAL FAILED + early-return
         (with combined output captured as `detail`).
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
        if dep.verify:
            code, out = run_verify(dep.verify)
            if code != 0:
                report.steps.append(
                    WizardStep(StepKind.MANUAL, dep.step, StepStatus.FAILED, detail=out.strip() or f"verify exited {code}")
                )
                return report
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

- [ ] **Step 4: Run wizard tests — expect 8 passed**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_wizard.py -v
```

Expected: 8 passed (5 original + 3 new).

- [ ] **Step 5: Wire `run_verify` in `omnireach/commands/setup.py` — replace entirely**

```python
"""omnireach setup <source> — conversational setup wizard."""

from __future__ import annotations

import asyncio
import subprocess

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


def _run_verify(cmd: str) -> tuple[int, str]:
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.returncode, (res.stdout or "") + (res.stderr or "")


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
            run_verify=_run_verify,
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

- [ ] **Step 6: Re-run setup CLI tests — expect 3 still passed (no behavior change since hackernews has no manual deps)**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_cmd_setup.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Full suite**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 75 passed (72 + 3 new wizard tests).

- [ ] **Step 8: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/wizard.py omnireach/commands/setup.py tests/test_wizard.py && git commit -m "feat(wizard): run dep.verify after manual step, fail-fast on non-zero exit"
```

---

## Task 2: OpenCLI installer helper

**Files:**
- Modify: `omnireach/commands/setup.py` (extend `_run_install` to support `chrome_extension` kind as a manual instruction)
- Modify: `tests/test_cmd_setup.py` (regression)

This task is small: OpenCLI's Chrome extension cannot be installed by Agent at all — the user must click in `chrome://extensions`. We don't try. But we want the wizard to recognize a `chrome_extension` kind in `deps.auto` so the registry stays declarative — when seen, it raises `InstallError` with a hint pointing to the Chrome Web Store URL. This way, the wizard reports the right failure with the right next-step hint without faking success.

Actually, on reflection: Chrome extension install is a **manual** step, not auto. So it belongs in `deps.manual` with a `verify: opencli doctor` line that confirms the extension is live. No installer change needed.

**This task is a no-op.** The wizard already handles `deps.manual` + `verify` correctly after Task 1. Skip and proceed.

(Note: this task is intentionally retained in the plan as a placeholder for future installer extensions, e.g., `pip install`, `cargo install`, `homebrew formula`. Anyone running v0.3 should know there's no new code here.)

---

## Task 3: Twitter adapter via OpenCLI

**Files:**
- Create: `omnireach/adapters/twitter.py`
- Create: `tests/adapters/test_twitter.py`

- [ ] **Step 1: Write `tests/adapters/test_twitter.py`**

```python
import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.twitter import TwitterAdapter


async def test_twitter_search_parses_opencli_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "text": "Claude 4.7 prompt caching is wild",
                "url": "https://twitter.com/alice/status/123",
                "author": "alice",
                "created_at": "2026-05-20T10:00:00Z",
                "like_count": 1234,
                "retweet_count": 56,
                "reply_count": 12,
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.twitter.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.twitter.shutil.which", lambda n: "/usr/bin/" + n)

    out = await TwitterAdapter().search("claude", limit=3)
    assert len(out) == 1
    assert out[0].source == "twitter"
    assert out[0].author == "alice"
    assert out[0].engagement.likes == 1234
    assert out[0].engagement.shares == 56
    assert out[0].engagement.comments == 12
    # title falls back to text since tweets have no title
    assert "Claude 4.7" in out[0].title


async def test_twitter_missing_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.twitter.shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable) as exc:
        await TwitterAdapter().search("x")
    assert "opencli" in str(exc.value).lower()


async def test_twitter_is_ready_requires_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.twitter.shutil.which", lambda n: "/usr/bin/opencli")
    assert await TwitterAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.twitter.shutil.which", lambda n: None)
    assert await TwitterAdapter().is_ready() is False
```

- [ ] **Step 2: Run — expect FAIL (module missing)**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/adapters/test_twitter.py -x
```

Expected: ImportError.

- [ ] **Step 3: Implement `omnireach/adapters/twitter.py`**

```python
"""Twitter / X adapter — shells out to OpenCLI, which uses a logged-in Chrome session.

Requires the `opencli` binary on PATH. The user must have:
  1. installed the OpenCLI Chrome Bridge extension from chrome.google.com
  2. logged into twitter.com in that Chrome profile

The wizard (omnireach setup twitter) walks the user through both manual steps
with `opencli doctor` and `opencli twitter state` as verify commands.
"""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


class TwitterAdapter(AdapterBase):
    name = "twitter"
    requires = ["opencli"]

    async def is_ready(self) -> bool:
        return shutil.which("opencli") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("opencli"):
            raise AdapterUnavailable(
                "twitter", "opencli not installed", hint="omnireach setup twitter"
            )

        proc = await asyncio.create_subprocess_exec(
            "opencli", "twitter", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("twitter", err.decode().strip() or "opencli twitter search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("twitter", f"opencli returned non-JSON: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            text = item.get("text", "") or ""
            title = (text[:80] + "…") if len(text) > 80 else text
            results.append(
                SearchResult(
                    source="twitter",
                    adapter="opencli",
                    title=title,
                    url=item.get("url", ""),
                    content=text,
                    author=item.get("author"),
                    ts=item.get("created_at"),
                    score=0.5,
                    engagement=Engagement(
                        likes=item.get("like_count"),
                        shares=item.get("retweet_count"),
                        comments=item.get("reply_count"),
                    ),
                    raw=item,
                )
            )
        return results
```

- [ ] **Step 4: Run twitter tests — expect 3 passed**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/adapters/test_twitter.py -v
```

- [ ] **Step 5: Full suite**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 78 passed (75 + 3).

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/adapters/twitter.py tests/adapters/test_twitter.py && git commit -m "feat(adapters): twitter via opencli logged-in Chrome"
```

---

## Task 4: 小红书 (Xiaohongshu) adapter via OpenCLI

**Files:**
- Create: `omnireach/adapters/xiaohongshu.py`
- Create: `tests/adapters/test_xiaohongshu.py`

- [ ] **Step 1: Write `tests/adapters/test_xiaohongshu.py`**

```python
import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.xiaohongshu import XiaohongshuAdapter


async def test_xhs_search_parses_opencli_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "Claude 4.7 上手 5 分钟入门",
                "url": "https://xiaohongshu.com/discovery/item/abc",
                "author": "AI小白",
                "content": "今天试了一下 Claude 4.7 …",
                "published_at": "2026-05-21T08:00:00Z",
                "like_count": 4200,
                "comment_count": 87,
                "collect_count": 256,
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.xiaohongshu.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda n: "/usr/bin/" + n)

    out = await XiaohongshuAdapter().search("claude", limit=3)
    assert len(out) == 1
    assert out[0].source == "xiaohongshu"
    assert out[0].author == "AI小白"
    assert out[0].engagement.likes == 4200
    assert out[0].engagement.comments == 87


async def test_xhs_missing_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable) as exc:
        await XiaohongshuAdapter().search("x")
    assert "opencli" in str(exc.value).lower()


async def test_xhs_is_ready_requires_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda n: "/usr/bin/opencli")
    assert await XiaohongshuAdapter().is_ready() is True

    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda n: None)
    assert await XiaohongshuAdapter().is_ready() is False
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/adapters/test_xiaohongshu.py -x
```

- [ ] **Step 3: Implement `omnireach/adapters/xiaohongshu.py`**

```python
"""小红书 (Xiaohongshu) adapter — shells out to OpenCLI's logged-in Chrome session.

Requires the `opencli` binary on PATH plus a Chrome profile logged into
xiaohongshu.com. The wizard (omnireach setup xiaohongshu) walks the user
through the Chrome extension install + xiaohongshu login.
"""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import Engagement, SearchResult


class XiaohongshuAdapter(AdapterBase):
    name = "xiaohongshu"
    requires = ["opencli"]

    async def is_ready(self) -> bool:
        return shutil.which("opencli") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("opencli"):
            raise AdapterUnavailable(
                "xiaohongshu", "opencli not installed", hint="omnireach setup xiaohongshu"
            )

        proc = await asyncio.create_subprocess_exec(
            "opencli", "xiaohongshu", "search", "--json", "--limit", str(limit), query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("xiaohongshu", err.decode().strip() or "opencli xiaohongshu search failed")

        try:
            data = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise AdapterUnavailable("xiaohongshu", f"opencli returned non-JSON: {e}")

        results: list[SearchResult] = []
        for item in data.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    source="xiaohongshu",
                    adapter="opencli",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    author=item.get("author"),
                    ts=item.get("published_at"),
                    score=0.5,
                    engagement=Engagement(
                        likes=item.get("like_count"),
                        comments=item.get("comment_count"),
                        shares=item.get("collect_count"),  # collects map to "shares" — closest semantic
                    ),
                    raw=item,
                )
            )
        return results
```

- [ ] **Step 4: Run xhs tests — expect 3 passed**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/adapters/test_xiaohongshu.py -v
```

- [ ] **Step 5: Full suite**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 81 passed (78 + 3).

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/adapters/xiaohongshu.py tests/adapters/test_xiaohongshu.py && git commit -m "feat(adapters): xiaohongshu via opencli logged-in Chrome"
```

---

## Task 5: Register twitter + xiaohongshu in sources.yml

**Files:**
- Modify: `omnireach/sources.yml`
- Modify: `tests/test_registry.py` (count 8 → 10 + new IDs)

- [ ] **Step 1: Update `tests/test_registry.py`**

Find `test_load_registry_returns_all_sources` and update:

```python
def test_load_registry_returns_all_sources():
    reg = load_registry()
    ids = [s.id for s in reg.sources]
    assert "hackernews" in ids
    assert "web" in ids
    assert "wechat" in ids
    assert "bilibili" in ids
    assert "reddit" in ids
    assert "twitter" in ids
    assert "xiaohongshu" in ids
    assert len(reg.sources) == 10
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_registry.py -x
```

- [ ] **Step 3: Append twitter + xiaohongshu entries to `omnireach/sources.yml`**

At the very end of the file, append:

```yaml

- id: twitter
  tier: heavy
  adapter: omnireach.adapters.twitter.TwitterAdapter
  description: Twitter / X 搜索 (登录态 Chrome, 通过 OpenCLI)
  query_hints: [twitter, "x.com", "推特"]
  default_in_auto: false
  deps:
    auto:
      - { kind: npm, name: "@jackwener/opencli" }
    manual:
      - { step: "在 Chrome Web Store 安装 OpenCLI 扩展: https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk (装完后启用 chrome://extensions 里的开发者模式)", verify: "opencli doctor" }
      - { step: "在 Chrome 中登录 Twitter / X 账号 (打开 twitter.com 完成登录)", verify: "opencli twitter state" }

- id: xiaohongshu
  tier: heavy
  adapter: omnireach.adapters.xiaohongshu.XiaohongshuAdapter
  description: 小红书 搜索 + 笔记内容 (登录态 Chrome, 通过 OpenCLI)
  query_hints: ["小红书", xiaohongshu, "种草", "笔记"]
  default_in_auto: false
  deps:
    auto:
      - { kind: npm, name: "@jackwener/opencli" }
    manual:
      - { step: "在 Chrome Web Store 安装 OpenCLI 扩展: https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk", verify: "opencli doctor" }
      - { step: "在 Chrome 中登录 小红书 账号 (打开 xiaohongshu.com 完成登录)", verify: "opencli xiaohongshu state" }
```

- [ ] **Step 4: Run registry tests — expect 5 passed**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest tests/test_registry.py -v
```

- [ ] **Step 5: Verify `omnireach sources` renders three tier tables**

```bash
cd ~/Projects/omnireach && omnireach sources
```

Expected: ✅ ready (7), 🟡 one_step (1), 🔴 heavy (2).

- [ ] **Step 6: Full suite**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 81 passed (test count unchanged; the registry test gained assertions but still counts as 1 test).

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/omnireach && git add omnireach/sources.yml tests/test_registry.py && git commit -m "feat(registry): add twitter + xiaohongshu (heavy tier, OpenCLI)"
```

---

## Task 6: README + tag v0.3.0-alpha

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the "支持的源" section in `README.md`**

Find the section:

```markdown
## 支持的源

✅ **零配置 (7 个)**: `web` · `hackernews` · `youtube` · `github` · `rss` · `wechat` (微信公众号) · `bilibili` (B 站)

🟡 **一步配置 (1 个, v0.2 新增)**: `reddit` — 跑 `omnireach setup reddit`, Agent 自动装 rdt-cli, 你完成 OAuth

🔴 计划中 (v0.3+): `twitter` · `xiaohongshu` (小红书)
```

Replace with:

```markdown
## 支持的源

✅ **零配置 (7 个)**: `web` · `hackernews` · `youtube` · `github` · `rss` · `wechat` (微信公众号) · `bilibili` (B 站)

🟡 **一步配置 (1 个)**: `reddit` — 跑 `omnireach setup reddit`, Agent 自动装 rdt-cli, 你完成 OAuth

🔴 **重配置 (2 个, v0.3 新增)**: `twitter` · `xiaohongshu` (小红书) — 跑 `omnireach setup twitter` / `omnireach setup xiaohongshu`, Agent 装 OpenCLI, 你装 Chrome 扩展 + 登录账号

📋 计划中 (v0.4+): 付费 booster (Tavily / Brave / Perplexity), 用户偏好层
```

- [ ] **Step 2: Final suite**

```bash
cd ~/Projects/omnireach && .venv/bin/pytest -q
```

Expected: 81 passed.

- [ ] **Step 3: CLI sanity**

```bash
cd ~/Projects/omnireach && omnireach --help && omnireach sources
```

Expected: 5 subcommands; sources shows three tier tables.

- [ ] **Step 4: Commit README**

```bash
cd ~/Projects/omnireach && git add README.md && git commit -m "docs: README for v0.3 (twitter + xiaohongshu via OpenCLI)"
```

- [ ] **Step 5: Tag v0.3.0-alpha**

```bash
cd ~/Projects/omnireach && git tag -a v0.3.0-alpha -m "omnireach v0.3.0-alpha — twitter + xiaohongshu via OpenCLI, wizard verify loop"
```

- [ ] **Step 6: Final branch summary**

```bash
cd ~/Projects/omnireach && git log --oneline main..feat/v0.3-twitter-xiaohongshu && git tag -l
```

Expected: 5 commits (Task 1 + Task 3 + Task 4 + Task 5 + Task 6); tags `v0.1.0-alpha`, `v0.2.0-alpha`, `v0.3.0-alpha`.

---

## Self-review notes

**Spec coverage check (§12 v0.3 row "解锁 reddit / twitter / 小红书 via OpenCLI + Chrome 扩展引导"):** Reddit was done in v0.2. Twitter (Task 3) + 小红书 (Task 4) covered. Chrome extension引导 is wired via Task 1's `verify` loop + sources.yml manual step pointing at chrome web store URL with `opencli doctor` as the verify command.

**Spec §8.2 "verify 命令自动跑, 挂了 wizard 重试或退出"** — Task 1 implements "挂了退出" (early-return on non-zero verify exit). The "重试" loop is not implemented in v0.3 — the user must re-run `omnireach setup <source>` to retry. This is a deliberate scope cut: a retry loop would need a "you want to retry? [y/n]" prompt that complicates the DI surface. The current "rerun the command" UX is friendly enough for v0.3.

**Type consistency check:**
- `RunVerifyFn` introduced in Task 1, used identically in tests + setup.py wiring (Task 1) — match.
- `Engagement.shares` used for Twitter retweets AND xhs collects — both are "amplification" signals, acceptable overload.
- All adapter names + sources.yml IDs match (`twitter`, `xiaohongshu`).
- `requires = ["opencli"]` (single binary) — both Twitter and xhs share this, distinct from Reddit's dual `["agent-reach", "rdt-cli"]`.

**Placeholder scan:** Every step has actual code or actual commands. Task 2 is intentionally a no-op (documented as such); not a placeholder, an explicit skip with rationale.

**Test count progression:** v0.2 baseline 72 → Task 1 (+3 = 75) → Task 3 (+3 = 78) → Task 4 (+3 = 81) → Tasks 5+6 (no change = 81).

**Anti-scope-creep:** User preferences layer + paid sources are explicitly deferred to v0.4. Wizard retry loop is also deferred. Stay focused.
