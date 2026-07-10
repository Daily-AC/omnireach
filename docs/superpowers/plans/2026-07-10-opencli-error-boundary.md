# OpenCLI Error Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop reporting OpenCLI runtime failures as unconfigured sources and expose their real details in TTY output.

**Architecture:** Add a focused `OpenCLICommandError` at the shared subprocess boundary. Missing OpenCLI remains `AdapterUnavailable`; nonzero exits and response-contract failures flow through the dispatcher's existing generic failure branch and the CLI's existing red error renderer.

**Tech Stack:** Python 3.10+, asyncio subprocesses, Click/Rich, Pydantic, pytest/pytest-asyncio, uv/hatchling.

---

### Task 1: Classify OpenCLI Runtime Errors

**Files:**
- Modify: `tests/adapters/test_opencli.py`
- Modify: `omnireach/adapters/_opencli.py`

- [ ] **Step 1: Write failing subprocess-boundary tests**

Import `OpenCLICommandError` and add tests that require a nonzero process, malformed JSON,
and invalid result shape to raise it. Keep missing binary on `AdapterUnavailable`:

```python
from omnireach.adapters._opencli import OpenCLICommandError, run_opencli_json


async def test_opencli_bridge_nonzero_is_execution_error(monkeypatch):
    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 1

            async def communicate(self):
                return b"", b"Chrome bridge disconnected"

        return P()

    monkeypatch.setattr("omnireach.adapters._opencli.shutil.which", lambda _: "/bin/opencli")
    monkeypatch.setattr(
        "omnireach.adapters._opencli.asyncio.create_subprocess_exec", fake_exec
    )

    with pytest.raises(OpenCLICommandError, match="Chrome bridge disconnected"):
        await run_opencli_json("douyin", "douyin", "search", "gpt5.6")


async def test_opencli_bridge_malformed_json_is_execution_error(monkeypatch):
    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return b"not-json", b""

        return P()

    monkeypatch.setattr("omnireach.adapters._opencli.shutil.which", lambda _: "/bin/opencli")
    monkeypatch.setattr(
        "omnireach.adapters._opencli.asyncio.create_subprocess_exec", fake_exec
    )

    with pytest.raises(OpenCLICommandError, match="non-JSON"):
        await run_opencli_json("douyin", "douyin", "search", "gpt5.6")


async def test_opencli_bridge_missing_binary_stays_unavailable(monkeypatch):
    monkeypatch.setattr("omnireach.adapters._opencli.shutil.which", lambda _: None)
    with pytest.raises(AdapterUnavailable, match="opencli not installed"):
        await run_opencli_json("douyin", "douyin", "search", "gpt5.6")
```

Change the existing wrong-shape test to expect `OpenCLICommandError`.

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
uv run pytest tests/adapters/test_opencli.py -q
```

Expected: import fails because `OpenCLICommandError` does not exist.

- [ ] **Step 3: Implement the new exception boundary**

Add to `omnireach/adapters/_opencli.py`:

```python
class OpenCLICommandError(RuntimeError):
    """OpenCLI is installed, but a command failed or broke its JSON contract."""

    def __init__(self, source: str, reason: str) -> None:
        super().__init__(f"opencli {source} command failed: {reason}")
        self.source = source
        self.reason = reason
```

Replace runtime `AdapterUnavailable` raises with:

```python
raise OpenCLICommandError(
    source, detail or "command exited with no error detail"
)
```

```python
raise OpenCLICommandError(source, f"returned non-JSON: {e}") from e
```

```python
raise OpenCLICommandError(source, "returned an invalid result shape")
```

Do not change the missing-binary branch.

- [ ] **Step 4: Verify GREEN and commit**

```bash
uv run pytest tests/adapters/test_opencli.py tests/adapters/test_douyin.py \
  tests/adapters/test_twitter.py tests/adapters/test_google.py -q
git add omnireach/adapters/_opencli.py tests/adapters/test_opencli.py
git commit -m "fix: classify OpenCLI command failures correctly"
```

Expected: all focused tests pass.

### Task 2: Lock Dispatcher and TTY Behavior

**Files:**
- Modify: `tests/test_dispatcher.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write a dispatcher classification test**

Add an adapter that raises `OpenCLICommandError` and assert `failed`:

```python
class _OpenCLIFailedAdapter(AdapterBase):
    name = "douyin"

    async def is_ready(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        raise OpenCLICommandError("douyin", "Chrome bridge disconnected")


def test_dispatcher_classifies_opencli_command_error_as_failed():
    results, errors = asyncio.run(
        Dispatcher(timeout=5.0).run({"douyin": _OpenCLIFailedAdapter()}, "q")
    )
    assert results == []
    assert errors[0].category == "failed"
    assert "Chrome bridge disconnected" in errors[0].error
```

- [ ] **Step 2: Write a TTY regression test for the user's symptom**

Monkeypatch the CLI service with a failed Douyin envelope:

```python
def test_tty_prints_opencli_runtime_failure_instead_of_unconfigured(monkeypatch):
    async def fake_search(*args, **kwargs):
        return SearchEnvelope(
            query="gpt5.6",
            ts="2026-07-10T00:00:00Z",
            errors=[
                SourceError(
                    source="douyin",
                    error="opencli douyin command failed: Chrome bridge disconnected",
                    category="failed",
                )
            ],
        )

    monkeypatch.setattr("omnireach.cli.search", fake_search)
    monkeypatch.setattr("omnireach.cli._should_emit_json", lambda _: False)
    result = CliRunner().invoke(main, ["search", "gpt5.6", "--on", "douyin"])

    assert "✗ douyin" in result.output
    assert "Chrome bridge disconnected" in result.output
    assert "源未配置" not in result.output
```

- [ ] **Step 3: Run both tests**

```bash
uv run pytest tests/test_dispatcher.py tests/test_cli.py -q
```

Expected: the tests pass without production changes because Task 1 now routes the exception
through established generic failure and TTY rendering branches. If either fails, change only
the responsible classification or rendering boundary.

- [ ] **Step 4: Commit the regression coverage**

```bash
git add tests/test_dispatcher.py tests/test_cli.py
git commit -m "test: cover OpenCLI runtime error reporting"
```

### Task 3: Version, Real E2E, and Release

**Files:**
- Modify: `omnireach/__init__.py`
- Modify: `pyproject.toml`
- Modify: `.claude-plugin/plugin.json`
- Modify: `uv.lock`
- Create: `docs/releases/v0.13.1-alpha.md`

- [ ] **Step 1: Bump all public versions**

Set runtime, project, and plugin versions to `0.13.1-alpha`, then run `uv lock`. Verify
`uv.lock` records `0.13.1a0`.

- [ ] **Step 2: Add release notes**

Document the reproduced symptom, the corrected unavailable-versus-failed boundary, the
unchanged silent-tab behavior, and the native bridge migration direction. Use this PyPI
install command:

```bash
uv tool install --force 'omnireach==0.13.1a0'
```

- [ ] **Step 3: Run complete verification**

```bash
uv run pytest -q
uvx ruff check omnireach/adapters/_opencli.py tests/adapters/test_opencli.py \
  tests/test_dispatcher.py tests/test_cli.py
git diff --check
```

Expected: complete suite and lint pass.

- [ ] **Step 4: Run real Douyin E2E**

```bash
omnireach search --on douyin --limit 3 --timeout 45 --json "gpt5.6"
```

Expected: at least one real result and `errors=[]`.

- [ ] **Step 5: Build and verify artifacts**

Build wheel and sdist into `dist/v0.13.1`, run `twine check`, install the wheel into a fresh
Python 3.12 environment, and verify `omnireach --version` reports `0.13.1-alpha`.

- [ ] **Step 6: Publish through PR and exact merged commit**

Push the branch, create and squash-merge a PR, tag the merged `origin/main` commit as
`v0.13.1-alpha`, create a GitHub prerelease with the verified artifacts, publish the same
files to PyPI using `PYPI_TOKEN` from `~/.secrets/vault.env`, and verify a fresh public
installation plus a real Douyin search.
