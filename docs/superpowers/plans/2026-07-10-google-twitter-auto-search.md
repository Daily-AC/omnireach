# Google and Twitter Auto Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make normal Omnireach searches return Google and connected Twitter/X results through silent OpenCLI-backed Chrome tabs, while preserving lightweight quick mode and exact explicit-source behavior.

**Architecture:** Add one focused Google adapter around the existing cancellation-safe OpenCLI bridge. Add a service-layer augmentation function that conditionally appends Google and Twitter only for non-explicit `auto` and `deep` searches when OpenCLI is installed, then keep the existing concurrent dispatcher, normalizer, and scorer unchanged.

**Tech Stack:** Python 3.10+, asyncio, Pydantic, Click, pytest/pytest-asyncio, OpenCLI 1.8.6, YAML source registry, uv/hatchling.

---

## Execution Order Note

Execute Task 1 first, then Task 3 Steps 1-4 to register Google before running the service
augmentation tests in Task 2. After Task 2, finish Task 3 Steps 5-9, then Tasks 4 and 5.
The service helper deliberately verifies that an optional source exists in the registry, so
running all of Task 2 before the registry slice would make the intended green state
impossible.

## File Map

- Create `omnireach/adapters/google.py`: normalize real OpenCLI Google rows into the stable search contract.
- Create `tests/adapters/test_google.py`: adapter contract, filtering, argument, and missing-dependency tests.
- Modify `omnireach/service.py`: conditionally add Google and Twitter to automatic non-quick searches.
- Modify `tests/test_service.py`: service augmentation behavior and integration boundary tests.
- Modify `omnireach/sources.yml`: register Google metadata, hints, trust, timeout, and setup requirements.
- Modify `tests/test_registry.py`: assert the sixteenth source and its registry fields.
- Modify `README.md`, `README.zh.md`, `skills/omnireach/SKILL.md`, and `skills/omnireach/references/cli.md`: document automatic Google/Twitter behavior and quick-mode boundary.
- Modify `omnireach/__init__.py`, `pyproject.toml`, `.claude-plugin/plugin.json`, and `uv.lock`: publish the feature as `0.13.0-alpha` / normalized `0.13.0a0`.
- Create `docs/releases/v0.13.0-alpha.md`: release notes and exact installation command.

### Task 1: Google Adapter

**Files:**
- Create: `tests/adapters/test_google.py`
- Create: `omnireach/adapters/google.py`

- [ ] **Step 1: Write failing Google adapter tests from the observed real response**

Create tests covering the four-field OpenCLI response, URL filtering, argv construction, and missing OpenCLI:

```python
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.google import GoogleAdapter


async def test_google_search_normalizes_real_opencli_shape(monkeypatch):
    async def fake_run(source, *args):
        assert source == "google"
        return [
            {
                "snippet": "Frontier intelligence for professional work.",
                "title": "GPT-5.6: Frontier intelligence",
                "type": "result",
                "url": "https://openai.com/index/gpt-5-6/",
            }
        ]

    monkeypatch.setattr("omnireach.adapters.google.run_opencli_json", fake_run)
    monkeypatch.setattr("omnireach.adapters.google.shutil.which", lambda _: "/bin/opencli")

    results = await GoogleAdapter().search("gpt5.6", limit=5)

    assert len(results) == 1
    assert results[0].source == "google"
    assert results[0].adapter == "opencli"
    assert results[0].title == "GPT-5.6: Frontier intelligence"
    assert results[0].url == "https://openai.com/index/gpt-5-6/"
    assert results[0].content == "Frontier intelligence for professional work."
    assert results[0].raw["type"] == "result"


async def test_google_search_skips_rows_without_external_http_url(monkeypatch):
    async def fake_run(source, *args):
        return [
            {"type": "paa", "title": "What is GPT-5.6?", "url": "", "snippet": ""},
            {"type": "result", "title": "Internal", "url": "javascript:void(0)", "snippet": ""},
            {"type": "snippet", "title": "Answer", "url": "https://example.com/a", "snippet": ""},
        ]

    monkeypatch.setattr("omnireach.adapters.google.run_opencli_json", fake_run)
    monkeypatch.setattr("omnireach.adapters.google.shutil.which", lambda _: "/bin/opencli")

    results = await GoogleAdapter().search("gpt5.6")

    assert [result.url for result in results] == ["https://example.com/a"]


async def test_google_search_invokes_silent_opencli_bridge(monkeypatch):
    captured = []

    async def fake_run(source, *args):
        captured.extend((source, *args))
        return []

    monkeypatch.setattr("omnireach.adapters.google.run_opencli_json", fake_run)
    monkeypatch.setattr("omnireach.adapters.google.shutil.which", lambda _: "/bin/opencli")

    await GoogleAdapter().search("vibe coding", limit=7)

    assert captured == ["google", "google", "search", "vibe coding", "--limit", "7"]


async def test_google_missing_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.google.shutil.which", lambda _: None)
    with pytest.raises(AdapterUnavailable, match="opencli"):
        await GoogleAdapter().search("gpt5.6")
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
uv run pytest tests/adapters/test_google.py -q
```

Expected: collection fails because `omnireach.adapters.google` does not exist.

- [ ] **Step 3: Implement the minimal Google adapter**

Create `omnireach/adapters/google.py`:

```python
"""Google Search adapter backed by OpenCLI's silent Chrome bridge."""

from __future__ import annotations

import shutil
from urllib.parse import urlparse

from omnireach.adapters._opencli import run_opencli_json
from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult


def _is_external_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class GoogleAdapter(AdapterBase):
    name = "google"
    requires = ["opencli"]

    async def is_ready(self) -> bool:
        return shutil.which("opencli") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("opencli"):
            raise AdapterUnavailable(
                "google", "opencli not installed", hint="omnireach setup google"
            )

        items = await run_opencli_json(
            "google", "google", "search", query, "--limit", str(limit)
        )
        results: list[SearchResult] = []
        for item in items:
            url = item.get("url")
            if not _is_external_http_url(url):
                continue
            results.append(
                SearchResult(
                    source="google",
                    adapter="opencli",
                    title=str(item.get("title") or ""),
                    url=str(url),
                    content=str(item.get("snippet") or ""),
                    score=0.5,
                    raw=item,
                )
            )
            if len(results) >= limit:
                break
        return results
```

- [ ] **Step 4: Run Google adapter tests and verify GREEN**

Run:

```bash
uv run pytest tests/adapters/test_google.py tests/adapters/test_opencli.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the adapter unit**

```bash
git add omnireach/adapters/google.py tests/adapters/test_google.py
git commit -m "feat: add Google search adapter"
```

### Task 2: Automatic Google and Twitter Selection

**Files:**
- Modify: `tests/test_service.py`
- Modify: `omnireach/service.py`

- [ ] **Step 1: Write failing augmentation tests**

Add tests for auto, quick, explicit, missing OpenCLI, and duplicate prevention:

```python
from omnireach.registry import load_registry
from omnireach.service import augment_with_active_browser_sources


def test_auto_search_adds_google_and_twitter_when_opencli_exists(monkeypatch):
    monkeypatch.setattr("omnireach.service.shutil.which", lambda _: "/bin/opencli")
    result = augment_with_active_browser_sources(
        ["hackernews"], load_registry(), explicit_sources=None, mode="auto"
    )
    assert result == ["hackernews", "google", "twitter"]


def test_quick_search_never_adds_browser_sources(monkeypatch):
    monkeypatch.setattr("omnireach.service.shutil.which", lambda _: "/bin/opencli")
    result = augment_with_active_browser_sources(
        ["hackernews"], load_registry(), explicit_sources=None, mode="quick"
    )
    assert result == ["hackernews"]


def test_explicit_sources_are_exact(monkeypatch):
    monkeypatch.setattr("omnireach.service.shutil.which", lambda _: "/bin/opencli")
    result = augment_with_active_browser_sources(
        ["hackernews"], load_registry(), explicit_sources=["hackernews"], mode="auto"
    )
    assert result == ["hackernews"]


def test_auto_search_skips_browser_sources_without_opencli(monkeypatch):
    monkeypatch.setattr("omnireach.service.shutil.which", lambda _: None)
    result = augment_with_active_browser_sources(
        ["hackernews"], load_registry(), explicit_sources=None, mode="auto"
    )
    assert result == ["hackernews"]


def test_auto_search_does_not_duplicate_browser_sources(monkeypatch):
    monkeypatch.setattr("omnireach.service.shutil.which", lambda _: "/bin/opencli")
    result = augment_with_active_browser_sources(
        ["google", "twitter"], load_registry(), explicit_sources=None, mode="deep"
    )
    assert result == ["google", "twitter"]
```

- [ ] **Step 2: Run the new service tests and verify RED**

Run:

```bash
uv run pytest tests/test_service.py -q
```

Expected: import fails because `augment_with_active_browser_sources` does not exist.

- [ ] **Step 3: Implement conditional source augmentation**

In `omnireach/service.py`, import `shutil`, define the optional source tuple and function,
then call it before booster augmentation:

```python
import shutil

AUTO_BROWSER_SOURCES = ("google", "twitter")


def augment_with_active_browser_sources(
    source_ids: list[str],
    registry: Registry,
    explicit_sources: list[str] | None,
    mode: str,
) -> list[str]:
    if explicit_sources or mode == "quick" or not shutil.which("opencli"):
        return list(source_ids)
    output = list(source_ids)
    for source_id in AUTO_BROWSER_SOURCES:
        try:
            registry.get(source_id)
        except KeyError:
            continue
        if source_id not in output:
            output.append(source_id)
    return output
```

Change the search flow to:

```python
    source_ids = augment_with_active_browser_sources(
        route.source_ids, registry, sources, mode
    )
    source_ids = augment_with_active_boosters(source_ids, registry, sources)
```

- [ ] **Step 4: Run service and routing tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_service.py tests/test_router.py tests/test_cli.py tests/test_mcp_server.py -q
```

Expected: all tests pass and explicit/quick behavior remains unchanged.

- [ ] **Step 5: Commit automatic selection**

```bash
git add omnireach/service.py tests/test_service.py
git commit -m "feat: auto-select connected Google and Twitter"
```

### Task 3: Registry, Documentation, and Version

**Files:**
- Modify: `omnireach/sources.yml`
- Modify: `tests/test_registry.py`
- Modify: `README.md`
- Modify: `README.zh.md`
- Modify: `skills/omnireach/SKILL.md`
- Modify: `skills/omnireach/references/cli.md`
- Modify: `omnireach/__init__.py`
- Modify: `pyproject.toml`
- Modify: `.claude-plugin/plugin.json`
- Modify: `uv.lock`
- Create: `docs/releases/v0.13.0-alpha.md`

- [ ] **Step 1: Write failing registry expectations**

Update `tests/test_registry.py` to require Google and sixteen total sources:

```python
    assert "google" in ids
    assert len(reg.sources) == 16
```

Add:

```python
def test_registry_has_google_heavy_source():
    google = load_registry().get("google")
    assert google.tier == "heavy"
    assert google.adapter.endswith("GoogleAdapter")
    assert google.default_in_auto is False
    assert google.trust == 0.85
    assert google.timeout_seconds == 15.0
    assert "google" in google.query_hints
    assert "谷歌" in google.query_hints
```

- [ ] **Step 2: Run registry tests and verify RED**

Run:

```bash
uv run pytest tests/test_registry.py -q
```

Expected: failures because Google is absent and the source count is fifteen.

- [ ] **Step 3: Register Google**

Insert this entry before Reddit in `omnireach/sources.yml`:

```yaml
- id: google
  tier: heavy
  adapter: omnireach.adapters.google.GoogleAdapter
  description: Google 网页搜索 (OpenCLI 后台临时 tab)
  query_hints: [google, "谷歌", "网页搜索"]
  default_in_auto: false
  trust: 0.85
  timeout_seconds: 15
  deps:
    auto:
      - { kind: npm, name: "github:Daily-AC/OpenCLI" }
    manual:
      - { step: "在 Chrome Web Store 安装 OpenCLI 扩展: https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk", verify: "opencli doctor" }
```

- [ ] **Step 4: Verify registry GREEN**

Run:

```bash
uv run pytest tests/test_registry.py tests/test_cmd_sources.py tests/test_doctor.py -q
```

Expected: all tests pass and source/doctor output includes Google.

- [ ] **Step 5: Update user and agent documentation**

Document these exact behavioral facts in both READMEs and both skill files:

```text
- Normal auto search includes Google and Twitter when OpenCLI is installed.
- Both use background ephemeral tabs that close after the command.
- quick mode remains browser-free.
- Explicit --on remains the exact source set.
```

Add Google to each source table as `heavy`, dependency `OpenCLI + Chrome extension`, and
description `Google SERP through a silent background tab`. Update command examples so
`omnireach search "..."` describes the automatic behavior.

- [ ] **Step 6: Bump all public versions to 0.13.0-alpha**

Set:

```python
__version__ = "0.13.0-alpha"
```

Set both project and plugin JSON versions to `0.13.0-alpha`, then run:

```bash
uv lock
```

Expected: `uv.lock` records normalized version `0.13.0a0`.

- [ ] **Step 7: Add release notes**

Create `docs/releases/v0.13.0-alpha.md` with:

```markdown
# v0.13.0-alpha - Google and connected Twitter in normal search

Normal `omnireach search` now adds Google and Twitter/X when OpenCLI is installed. Both
sources reuse the connected Chrome profile through background ephemeral tabs and close them
after each command. `--mode quick` remains browser-free, and explicit `--on` remains exact.

Install or upgrade:

```bash
uv tool install --force 'omnireach==0.13.0a0'
```
```

Include the real verification commands and note that direct HTTP Google SERP scraping and
the retiring Custom Search JSON API were intentionally rejected.

- [ ] **Step 8: Run metadata, skill, and documentation checks**

Run:

```bash
uv run pytest tests/test_registry.py tests/test_version_metadata.py tests/test_skill_manifest.py -q
git diff --check
```

Expected: all tests pass and diff check is silent.

- [ ] **Step 9: Commit registry, docs, and version**

```bash
git add omnireach/sources.yml tests/test_registry.py README.md README.zh.md \
  skills/omnireach/SKILL.md skills/omnireach/references/cli.md \
  omnireach/__init__.py pyproject.toml .claude-plugin/plugin.json uv.lock \
  docs/releases/v0.13.0-alpha.md
git commit -m "docs: document automatic Google and Twitter search"
```

### Task 4: Full Verification and Real Upstream Tests

**Files:**
- No production file changes unless a real response exposes a contract bug; any such fix
  requires a new failing regression test before modification.

- [ ] **Step 1: Run focused adapter and routing tests**

```bash
uv run pytest tests/adapters/test_google.py tests/adapters/test_twitter.py \
  tests/adapters/test_opencli.py tests/test_service.py tests/test_router.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run the complete suite and lint changed Python files**

```bash
uv run pytest -q
uvx ruff check omnireach/adapters/google.py omnireach/service.py \
  tests/adapters/test_google.py tests/test_service.py tests/test_registry.py
```

Expected: all tests pass and Ruff reports no issues.

- [ ] **Step 3: Run real Google and Twitter searches**

```bash
uv run omnireach search --on google --limit 5 --timeout 45 --json "gpt5.6"
uv run omnireach search --on twitter --limit 5 --timeout 45 --json "gpt5.6"
```

Expected: each envelope has at least one result, no errors, and real HTTP(S) URLs. Copy the
observed Google response shape into the test fixture if it differs from the pre-implementation
observation.

- [ ] **Step 4: Run the real automatic search**

```bash
uv run omnireach search --limit 5 --timeout 45 --json "gpt5.6"
```

Expected: result source counts include both `google` and `twitter`, with no source-level
Google or Twitter errors.

- [ ] **Step 5: Verify visible Chrome state is unchanged**

Record visible Chrome windows and tabs with a read-only AppleScript before and after the
automatic command:

```bash
osascript -e 'tell application "Google Chrome" to return {count of windows, count of tabs of every window}'
```

Expected: the before and after visible counts are identical, and no Google or Twitter search
tab remains.

- [ ] **Step 6: Build and install the release artifact**

```bash
rm -rf dist/v0.13
uv build --out-dir dist/v0.13
uv venv --python 3.12 /tmp/omnireach-v013-verify
uv pip install --python /tmp/omnireach-v013-verify/bin/python \
  --force-reinstall dist/v0.13/omnireach-0.13.0a0-py3-none-any.whl
/tmp/omnireach-v013-verify/bin/omnireach --version
```

Expected: build succeeds and the installed CLI reports `0.13.0-alpha`.

### Task 5: Publish the Reviewed Unit

**Files:**
- Git/GitHub/PyPI release state only.

- [ ] **Step 1: Push and create the pull request**

```bash
git push -u origin codex/google-twitter-auto
gh pr create --base main --head codex/google-twitter-auto \
  --title "[codex] add Google and connected Twitter to normal search" \
  --body-file docs/releases/v0.13.0-alpha.md
```

Expected: PR URL is returned.

- [ ] **Step 2: Verify PR state and merge**

```bash
gh pr view --json state,mergeable,statusCheckRollup,url
gh pr merge --squash --delete-branch
```

Expected: PR is mergeable, required checks pass or none are configured, and state becomes
`MERGED`.

- [ ] **Step 3: Tag and publish GitHub Release from merged main**

Create annotated tag `v0.13.0-alpha` at the merged `origin/main`, push it, and create a
prerelease using `docs/releases/v0.13.0-alpha.md` plus wheel and sdist assets.

- [ ] **Step 4: Publish exact verified artifacts to PyPI**

Source `~/.secrets/vault.env`, pass `PYPI_TOKEN` only through Twine or uv's environment,
and upload the two artifacts from `dist/v0.13`. Never echo the token.

- [ ] **Step 5: Verify public installation**

Create a fresh Python 3.12 environment and install with:

```bash
uv pip install --python /tmp/omnireach-v013-public/bin/python \
  --no-cache 'omnireach==0.13.0a0'
```

Expected: public PyPI installation succeeds and `omnireach --version` reports
`0.13.0-alpha`.
