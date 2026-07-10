# Agent Fast Path MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose omnireach search and fetch as dependency-free MCP tools and make them the agent's preferred read-only web path before Playwright.

**Architecture:** Extract terminal-independent search and fetch services shared by Click and a minimal newline-delimited JSON-RPC stdio server. Register that server through the plugin, then tighten the skill so MCP is preferred, CLI is the fallback, and browser automation is reserved for interaction and visual work.

**Tech Stack:** Python 3.10+, Click, Pydantic v2, asyncio, stdlib JSON-RPC over stdio, pytest, Claude Code plugin `.mcp.json`.

---

## File Map

- Create `omnireach/service.py`: search orchestration shared by CLI and MCP.
- Create `omnireach/fetcher.py`: typed fetch orchestration and existing backend implementations.
- Create `omnireach/mcp_server.py`: minimal MCP protocol, tool schemas, argument validation, and stdio loop.
- Modify `omnireach/contract.py`: add `FetchEnvelope`.
- Modify `omnireach/cli.py`: render service results and register `mcp`.
- Modify `omnireach/commands/fetch.py`: reduce to Click rendering over `fetcher.fetch`.
- Create `tests/test_service.py`: search and fetch service contracts.
- Create `tests/test_mcp_server.py`: protocol and tool unit tests.
- Create `tests/test_mcp_process.py`: real stdio lifecycle test.
- Modify `tests/test_cli.py` and `tests/test_cmd_fetch.py`: lock CLI parity after extraction.
- Create `.mcp.json`: plugin MCP registration.
- Modify `.claude-plugin/plugin.json`: use the current author schema and automatic component discovery.
- Modify `skills/omnireach/SKILL.md`: MCP-first tool policy.
- Create `skills/omnireach/references/cli.md`: detailed CLI fallback reference.
- Modify `tests/test_skill_manifest.py`: validate MCP registration and routing policy.
- Modify `install.sh`: install the skill reference alongside `SKILL.md`.
- Modify `README.md` and `README.zh.md`: document MCP setup and Playwright boundary.

### Task 0: Preserve the verified dependency and browser fixes as a baseline

**Files:**
- Commit: all currently modified runtime, test, lock, and documentation files except this plan

- [ ] **Step 1: Re-run the verified baseline suite**

Run: `uv run pytest -q`

Expected: `289 passed` with exit code 0.

- [ ] **Step 2: Re-run static and upstream contract checks**

Run: `uvx ruff check omnireach`

Expected: `All checks passed!`

Run: `git diff --check`

Expected: no output and exit code 0.

Run: `bash scripts/verify-adapter-contracts.sh`

Expected: every installed CLI, including `opencli reddit search`, reports `argv OK`.

- [ ] **Step 3: Commit only the baseline fixes**

```bash
git add skills/omnireach/SKILL.md CLAUDE.md README.md README.zh.md \
  omnireach pyproject.toml scripts/verify-adapter-contracts.sh tests uv.lock
git commit -m "fix: make fetch and Chrome-backed search lightweight"
```

Expected: the commit contains the existing HTTP fetch, silent OpenCLI, Reddit, WeChat,
Twitter, and Xiaohongshu fixes, while the implementation plan remains uncommitted.

### Task 1: Add typed application services and preserve CLI behavior

**Files:**
- Create: `omnireach/fetcher.py`
- Create: `omnireach/service.py`
- Modify: `omnireach/contract.py`
- Modify: `omnireach/commands/fetch.py`
- Modify: `omnireach/cli.py`
- Create: `tests/test_service.py`
- Modify: `tests/test_cmd_fetch.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing typed fetch service tests**

Add to `tests/test_service.py`:

```python
from omnireach.contract import FetchEnvelope
from omnireach.fetcher import fetch


def test_fetch_service_returns_typed_success(monkeypatch):
    monkeypatch.setattr(
        "omnireach.fetcher._fetch_via_http",
        lambda url, timeout: "# service body",
    )

    result = fetch("https://example.com", backend="auto", timeout=5)

    assert isinstance(result, FetchEnvelope)
    assert result.backend == "http"
    assert result.content_markdown == "# service body"
    assert result.errors == []


def test_fetch_service_preserves_attempt_errors(monkeypatch):
    monkeypatch.setattr(
        "omnireach.fetcher._fetch_via_http",
        lambda url, timeout: (_ for _ in ()).throw(RuntimeError("blocked")),
    )
    monkeypatch.setattr(
        "omnireach.fetcher._fetch_via_jina",
        lambda url, timeout: "# fallback",
    )

    result = fetch("https://example.com")

    assert result.backend == "jina"
    assert result.content_markdown == "# fallback"
    assert result.errors == ["http: blocked"]
```

- [ ] **Step 2: Run the fetch service tests and verify RED**

Run: `uv run pytest -q tests/test_service.py`

Expected: collection fails because `FetchEnvelope` and `omnireach.fetcher` do not exist.

- [ ] **Step 3: Add `FetchEnvelope` and move fetch orchestration**

Add to `omnireach/contract.py`:

```python
class FetchEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    backend: Literal["http", "jina", "crwl", "opencli"] | None = None
    fetched_at: str
    content_markdown: str = ""
    errors: list[str] = Field(default_factory=list)
```

Move the backend constants and functions from `commands/fetch.py` into
`omnireach/fetcher.py`, then add:

```python
def fetch(url: str, *, backend: str = "auto", timeout: float = 30.0) -> FetchEnvelope:
    content = ""
    used_backend = None
    errors: list[str] = []
    for name in _resolve_backends(url, backend):
        try:
            candidate = _BACKENDS[name](url, timeout)
            suspicious, keyword = _looks_like_captcha(candidate)
            if suspicious:
                errors.append(
                    f"{name}: captcha_suspected: response contains "
                    f"verification-page keyword '{keyword}'"
                )
                continue
            content = candidate
            used_backend = name
            break
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")
    return FetchEnvelope(
        url=url,
        backend=used_backend,
        fetched_at=_now_iso(),
        content_markdown=content,
        errors=errors,
    )
```

Keep the backend map explicit:

```python
_BACKENDS = {
    "http": _fetch_via_http,
    "jina": _fetch_via_jina,
    "crwl": _fetch_via_crwl,
    "opencli": _fetch_via_opencli_weixin,
}
```

- [ ] **Step 4: Run the fetch service tests and verify GREEN**

Run: `uv run pytest -q tests/test_service.py`

Expected: 2 tests pass.

- [ ] **Step 5: Write failing search service tests**

Add to `tests/test_service.py`:

```python
import pytest

from omnireach.contract import SearchResult
from omnireach.service import search


@pytest.mark.asyncio
async def test_search_service_returns_ranked_envelope(monkeypatch):
    async def fake_search(self, query, *, limit=10):
        return [
            SearchResult(
                source="hackernews",
                adapter="builtin",
                title="service result",
                url="https://example.com/result",
                score=0.5,
            )
        ]

    monkeypatch.setattr(
        "omnireach.adapters.hackernews.HackerNewsAdapter.search",
        fake_search,
    )

    envelope = await search(
        "claude", sources=["hackernews"], limit=1, timeout=5
    )

    assert envelope.query == "claude"
    assert [result.source for result in envelope.results] == ["hackernews"]
    assert envelope.errors == []


@pytest.mark.asyncio
async def test_search_service_rejects_unknown_explicit_source():
    with pytest.raises(ValueError, match="unknown source"):
        await search("claude", sources=["not-a-source"])
```

- [ ] **Step 6: Run the search service tests and verify RED**

Run: `uv run pytest -q tests/test_service.py::test_search_service_returns_ranked_envelope tests/test_service.py::test_search_service_rejects_unknown_explicit_source`

Expected: import fails because `omnireach.service` does not exist.

- [ ] **Step 7: Implement the shared search service**

Create `omnireach/service.py` with the existing CLI orchestration:

```python
from __future__ import annotations

import os

from omnireach.contract import SearchEnvelope, SourceError
from omnireach.dispatcher import Dispatcher
from omnireach.normalizer import build_envelope
from omnireach.registry import load_registry
from omnireach.router import RouteRequest, Router
from omnireach.scorer import rank


_BOOSTER_KEY_ENV = {
    "tavily": "TAVILY_API_KEY",
    "brave": "BRAVE_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "exa": "EXA_API_KEY",
    "wechat": "EXA_API_KEY",
    "bilibili": "EXA_API_KEY",
}


def augment_with_active_boosters(source_ids, reg, explicit_sources):
    if explicit_sources:
        return list(source_ids)
    output = list(source_ids)
    for source_id, env_name in _BOOSTER_KEY_ENV.items():
        if not os.environ.get(env_name) or source_id in output:
            continue
        try:
            reg.get(source_id)
        except KeyError:
            continue
        output.append(source_id)
    return output


async def search(
    query: str,
    *,
    sources: list[str] | None = None,
    mode: str = "auto",
    limit: int = 10,
    timeout: float = 30.0,
) -> SearchEnvelope:
    reg = load_registry()
    if sources:
        unknown = [source for source in sources if source not in {s.id for s in reg.sources}]
        if unknown:
            raise ValueError(f"unknown source: {', '.join(unknown)}")
    route = Router(reg).plan(
        RouteRequest(query=query, explicit_sources=sources, mode=mode)
    )
    source_ids = augment_with_active_boosters(route.source_ids, reg, sources)
    adapters = {}
    load_errors: list[SourceError] = []
    for source_id in source_ids:
        try:
            spec = reg.get(source_id)
            adapters[source_id] = spec.load_adapter_class()()
        except Exception as exc:  # noqa: BLE001
            load_errors.append(
                SourceError(source=source_id, error=f"adapter load failed: {exc}")
            )
    dispatcher = Dispatcher(
        timeout=timeout,
        per_source_limit=limit,
        timeouts_by_source={s.id: s.timeout_seconds for s in reg.sources},
    )
    results, errors = await dispatcher.run(adapters, query)
    ranked = rank(results, trust_map={s.id: s.trust for s in reg.sources})
    return build_envelope(query=query, results=ranked, errors=[*load_errors, *errors])
```

Move `_augment_with_active_boosters` into `service.py` as
`augment_with_active_boosters`, then import it into `cli.py` under the existing private
name for compatibility with current tests:

```python
from omnireach.service import (
    augment_with_active_boosters as _augment_with_active_boosters,
)
```

- [ ] **Step 8: Refactor Click handlers onto the services**

In `commands/fetch.py`, import and re-export the backend helpers from `fetcher.py` so
existing callers continue to work, then render `fetcher.fetch(...)` and use
`result.model_dump_json()` for JSON output.

In `cli.py`, replace the orchestration block with:

```python
explicit = [s.strip() for s in on_.split(",") if s.strip()] if on_ else None
if explicit:
    known = {spec.id for spec in load_registry().sources}
    unknown = [source for source in explicit if source not in known]
    for source in unknown:
        click.echo(
            f"warning: 未知源 '{source}' — 跳过 (用 `omnireach sources` 查看可用源)",
            err=True,
        )
    explicit = [source for source in explicit if source in known]
    if not explicit:
        raise click.UsageError("没有有效的 source")
envelope = asyncio.run(
    search(
        query,
        sources=explicit,
        mode=mode,
        limit=limit,
        timeout=timeout,
    )
)
ranked = envelope.results
errors = envelope.errors
```

This keeps CLI's forgiving mixed-source behavior while MCP calls use the service directly
and receive `-32602` for any unknown source.

- [ ] **Step 9: Run service and CLI tests**

Run: `uv run pytest -q tests/test_service.py tests/test_cli.py tests/test_cmd_fetch.py`

Expected: all tests pass and existing CLI JSON fields remain unchanged.

- [ ] **Step 10: Commit the service extraction**

```bash
git add omnireach/contract.py omnireach/fetcher.py omnireach/service.py \
  omnireach/cli.py omnireach/commands/fetch.py \
  tests/test_service.py tests/test_cli.py tests/test_cmd_fetch.py
git commit -m "refactor: share search and fetch application services"
```

### Task 2: Implement the dependency-free MCP protocol and tools

**Files:**
- Create: `omnireach/mcp_server.py`
- Modify: `omnireach/cli.py`
- Create: `tests/test_mcp_server.py`

- [ ] **Step 1: Write failing MCP discovery tests**

Create `tests/test_mcp_server.py`:

```python
from omnireach.mcp_server import handle_message


def test_initialize_advertises_static_tools():
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"},
        },
    })

    assert response["id"] == 1
    assert response["result"]["protocolVersion"] == "2025-06-18"
    assert response["result"]["capabilities"] == {"tools": {"listChanged": False}}


def test_tools_list_exposes_search_and_fetch():
    response = handle_message({
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}
    })

    tools = {tool["name"]: tool for tool in response["result"]["tools"]}
    assert set(tools) == {"omnireach_search", "omnireach_fetch"}
    assert tools["omnireach_search"]["inputSchema"]["required"] == ["query"]
    assert tools["omnireach_fetch"]["annotations"]["readOnlyHint"] is True
```

- [ ] **Step 2: Run MCP discovery tests and verify RED**

Run: `uv run pytest -q tests/test_mcp_server.py`

Expected: collection fails because `omnireach.mcp_server` does not exist.

- [ ] **Step 3: Implement protocol constants, tool schemas, and discovery**

Create `omnireach/mcp_server.py` with:

```python
PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "omnireach", "version": __version__}
TOOL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

TOOLS = [
    {
        "name": "omnireach_search",
        "title": "Search the web with omnireach",
        "description": (
            "Search web and vertical platforms. Login-backed sources may read the "
            "user's Chrome session through a hidden ephemeral tab."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "sources": {"type": "array", "items": {"type": "string"}},
                "mode": {"type": "string", "enum": ["auto", "quick", "deep"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                "timeout": {"type": "number", "minimum": 1, "maximum": 120},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": TOOL_ANNOTATIONS,
    },
    {
        "name": "omnireach_fetch",
        "title": "Fetch a page with omnireach",
        "description": (
            "Read an HTTP(S) URL as Markdown. Ordinary pages avoid Chrome; supported "
            "login-walled pages may use a hidden ephemeral Chrome tab."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "format": "uri"},
                "backend": {
                    "type": "string",
                    "enum": ["auto", "http", "jina", "crwl", "opencli"],
                },
                "timeout": {"type": "number", "minimum": 1, "maximum": 120},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        "annotations": TOOL_ANNOTATIONS,
    },
]
```

Implement `handle_message` for `initialize`, `ping`, `tools/list`, and notifications.
Use helpers `_result(id_, value)` and `_error(id_, code, message)` so every response is a
single JSON-RPC 2.0 object. Return `None` for notifications.

- [ ] **Step 4: Run MCP discovery tests and verify GREEN**

Run: `uv run pytest -q tests/test_mcp_server.py`

Expected: discovery tests pass.

- [ ] **Step 5: Write failing tool-call and validation tests**

Add to `tests/test_mcp_server.py`:

```python
import json


def test_search_tool_returns_structured_and_text_content(monkeypatch):
    async def fake_search(**kwargs):
        from omnireach.contract import SearchEnvelope
        return SearchEnvelope(query="q", ts="2026-07-10T00:00:00Z")

    monkeypatch.setattr("omnireach.mcp_server.search", fake_search)
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "omnireach_search", "arguments": {"query": "q"}},
    })

    result = response["result"]
    assert result["structuredContent"]["query"] == "q"
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    assert result["isError"] is False


def test_fetch_exhaustion_is_a_tool_error(monkeypatch):
    from omnireach.contract import FetchEnvelope

    monkeypatch.setattr(
        "omnireach.mcp_server.fetch",
        lambda **kwargs: FetchEnvelope(
            url=kwargs["url"],
            fetched_at="2026-07-10T00:00:00Z",
            errors=["http: blocked"],
        ),
    )
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "omnireach_fetch",
            "arguments": {"url": "https://example.com"},
        },
    })

    assert response["result"]["isError"] is True
    assert response["result"]["structuredContent"]["errors"] == ["http: blocked"]


def test_invalid_tool_arguments_return_minus_32602():
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "omnireach_fetch", "arguments": {"url": "file:///tmp/x"}},
    })

    assert response["error"]["code"] == -32602
```

- [ ] **Step 6: Run tool-call tests and verify RED**

Run: `uv run pytest -q tests/test_mcp_server.py`

Expected: failures because `tools/call` and argument validation are not implemented.

- [ ] **Step 7: Implement tool calls and validation**

Add strict validators that reject booleans as numbers, unknown properties, empty queries,
non-HTTP(S) URLs, unknown source IDs, and values outside schema bounds. Dispatch search
with `asyncio.run(search(...))` and fetch synchronously.

Build results with:

```python
def _tool_result(payload: dict, *, is_error: bool = False) -> dict:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": payload,
        "isError": is_error,
    }
```

Convert validation failures to JSON-RPC `-32602`. Convert expected service exceptions to a
tool result with `isError: true`; reserve `-32603` for defects outside normal execution.

- [ ] **Step 8: Register and test the `mcp` Click command**

Add:

```python
@click.command("mcp")
def mcp_cmd() -> None:
    """Run the omnireach MCP server over stdio."""
    serve_stdio()
```

Register it with `main.add_command(mcp_cmd)` in `cli.py`. Add a CLI help assertion that
`mcp` appears in `omnireach --help`.

- [ ] **Step 9: Run MCP and CLI tests**

Run: `uv run pytest -q tests/test_mcp_server.py tests/test_cli.py`

Expected: all tests pass.

- [ ] **Step 10: Commit the MCP server**

```bash
git add omnireach/mcp_server.py omnireach/cli.py tests/test_mcp_server.py tests/test_cli.py
git commit -m "feat: expose search and fetch over MCP"
```

### Task 3: Verify the real stdio process lifecycle

**Files:**
- Create: `tests/test_mcp_process.py`

- [ ] **Step 1: Write the failing process-level lifecycle test**

Create `tests/test_mcp_process.py` using `subprocess.Popen` with text pipes. Send compact
single-line JSON for `initialize`, `notifications/initialized`, `tools/list`, and
`tools/call`. Use `select.select` on POSIX to assert that the notification produces no
stdout response. Close stdin and require exit code 0 within five seconds.

Use `omnireach_fetch` with `backend: "http"` against a local `http.server.ThreadingHTTPServer`
fixture that serves a deterministic HTML article, so this process test exercises real HTTP
and HTML-to-Markdown without internet access.

Assertions:

```python
assert init["result"]["protocolVersion"] == "2025-06-18"
assert {tool["name"] for tool in listed["result"]["tools"]} == {
    "omnireach_search", "omnireach_fetch"
}
assert called["result"]["structuredContent"]["backend"] == "http"
assert "MCP process article" in called["result"]["structuredContent"]["content_markdown"]
assert proc.wait(timeout=5) == 0
```

- [ ] **Step 2: Run the process test and verify RED**

Run: `uv run pytest -q tests/test_mcp_process.py`

Expected: failure because `serve_stdio` does not yet implement the complete line loop or
clean EOF shutdown.

- [ ] **Step 3: Implement the stdio loop**

Implement `serve_stdio(stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)`:

```python
def serve_stdio(stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr) -> None:
    for line in stdin:
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _error(None, -32700, f"Parse error: {exc.msg}")
        else:
            try:
                response = handle_message(message)
            except Exception as exc:  # noqa: BLE001
                print(f"omnireach MCP internal error: {exc}", file=stderr)
                response = _error(message.get("id"), -32603, "Internal error")
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
            stdout.write("\n")
            stdout.flush()
```

Do not initialize Rich consoles or write startup banners to stdout.

- [ ] **Step 4: Run process and protocol tests**

Run: `uv run pytest -q tests/test_mcp_process.py tests/test_mcp_server.py`

Expected: all tests pass with no leaked process.

- [ ] **Step 5: Commit the process contract**

```bash
git add omnireach/mcp_server.py tests/test_mcp_process.py
git commit -m "test: verify MCP stdio lifecycle"
```

### Task 4: Register the MCP server and enforce agent routing

**Files:**
- Create: `.mcp.json`
- Modify: `.claude-plugin/plugin.json`
- Modify: `skills/omnireach/SKILL.md`
- Create: `skills/omnireach/references/cli.md`
- Modify: `install.sh`
- Modify: `tests/test_skill_manifest.py`

- [ ] **Step 1: Write failing plugin and skill policy tests**

Add to `tests/test_skill_manifest.py`:

```python
def test_plugin_registers_omnireach_mcp_server():
    data = json.loads((PROJECT_ROOT / ".mcp.json").read_text())
    server = data["mcpServers"]["omnireach"]
    assert server == {"command": "omnireach", "args": ["mcp"]}


def test_skill_requires_mcp_before_browser_automation():
    text = (
        PROJECT_ROOT / "skills" / "omnireach" / "SKILL.md"
    ).read_text().lower()
    assert "omnireach_search" in text
    assert "omnireach_fetch" in text
    assert "playwright" in text
    assert text.index("omnireach_search") < text.index("playwright")


def test_skill_cli_reference_exists_and_is_installed():
    reference = (
        PROJECT_ROOT / "skills" / "omnireach" /
        "references" / "cli.md"
    )
    assert reference.exists()
    install = (PROJECT_ROOT / "install.sh").read_text()
    assert "references/cli.md" in install
```

- [ ] **Step 2: Run plugin tests and verify RED**

Run: `uv run pytest -q tests/test_skill_manifest.py`

Expected: failures because `.mcp.json`, the reference, and MCP-first policy do not exist.

- [ ] **Step 3: Add plugin MCP registration**

Create `.mcp.json`:

```json
{
  "mcpServers": {
    "omnireach": {
      "command": "omnireach",
      "args": ["mcp"]
    }
  }
}
```

- [ ] **Step 4: Rewrite the skill around tool choice**

Keep the frontmatter description explicit about these triggers: researching the web,
searching Twitter/Reddit/Xiaohongshu/WeChat/Douyin/Bilibili, reading a URL, fetching an
article, or avoiding Playwright for read-only work.

Put this policy before command examples:

```markdown
## Tool Choice Policy

1. Call `omnireach_search` first for research or platform search.
2. Call `omnireach_fetch` first to read an HTTP or HTTPS URL.
3. Use the CLI fallback only when the MCP tools are unavailable.
4. Use Playwright or browser control only for clicks, forms, uploads, downloads,
   screenshots, visual inspection, or unsupported interactive workflows.

Do not launch Playwright merely to search or extract readable page content.
```

Move detailed CLI flags, envelope examples, doctor output, and pipeline examples into
`references/cli.md`. Keep `SKILL.md` imperative and under 2,000 words. Link the reference
from an `Additional Resources` section.

- [ ] **Step 5: Install the reference with the standalone skill**

After downloading `SKILL.md`, update `install.sh` to create `${SKILL_DIR}/references` and
download `skills/omnireach/references/cli.md`. A reference download failure
must print a warning but leave the installed CLI usable.

- [ ] **Step 6: Run skill and installer tests**

Run: `uv run pytest -q tests/test_skill_manifest.py tests/test_installer.py`

Expected: all tests pass.

Run: `sh scripts/verify-install.sh`

Expected: `PASS: verify-install static checks`.

- [ ] **Step 7: Commit plugin integration**

```bash
git add .mcp.json skills/omnireach install.sh \
  tests/test_skill_manifest.py
git commit -m "feat: register MCP tools and prefer them in the skill"
```

### Task 5: Document the MCP fast path and Playwright boundary

**Files:**
- Modify: `README.md`
- Modify: `README.zh.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add English and Chinese MCP usage sections**

Document:

```bash
# MCP client command
omnireach mcp

# Equivalent CLI fallback
omnireach search --json "query"
omnireach fetch --json "https://example.com/article"
```

Explain that plugin users receive `omnireach_search` and `omnireach_fetch`, ordinary fetch
does not start Chrome, login-backed adapters use hidden ephemeral tabs, and Playwright is
still required for interaction and visual verification.

- [ ] **Step 2: Update architecture notes**

Record the service boundary, zero-dependency MCP transport, tool names, and routing policy
in `CLAUDE.md`. Remove stale statements that say agents should always invoke the CLI.

- [ ] **Step 3: Verify documentation consistency**

Run: `rg -n "omnireach_search|omnireach_fetch|Playwright|omnireach mcp" README.md README.zh.md CLAUDE.md skills/omnireach`

Expected: both tool names and the Playwright boundary appear in both READMEs and the skill.

Run: `git diff --check`

Expected: no output and exit code 0.

- [ ] **Step 4: Commit documentation**

```bash
git add README.md README.zh.md CLAUDE.md
git commit -m "docs: explain the MCP fast path"
```

### Task 6: Full package and real MCP verification

**Files:**
- Modify only if verification exposes a reproducible defect

- [ ] **Step 1: Run the complete automated suite**

Run: `uv run pytest -q`

Expected: all tests pass with zero failures.

Run: `uvx ruff check omnireach`

Expected: `All checks passed!`

Run: `git diff --check`

Expected: no output and exit code 0.

- [ ] **Step 2: Validate plugin and upstream CLI contracts**

Run: `sh scripts/verify-install.sh`

Expected: `PASS: verify-install static checks`.

Run: `bash scripts/verify-adapter-contracts.sh`

Expected: all installed upstream CLIs report `argv OK`.

- [ ] **Step 3: Build distribution artifacts**

Run: `uv build --sdist --wheel --out-dir /tmp/omnireach-mcp-dist`

Expected: one `.tar.gz` and one `.whl` are built successfully.

Inspect the wheel metadata:

```bash
unzip -p /tmp/omnireach-mcp-dist/omnireach-*.whl '*/METADATA' | rg '^Requires-Dist:'
```

Expected: no `mcp`, `fastmcp`, `playwright`, `crawl4ai`, `lxml`, or `cssselect` runtime
dependency.

- [ ] **Step 4: Run a built-wheel MCP handshake and public fetch**

Launch the wheel entry point with:

```bash
uvx --refresh --from /tmp/omnireach-mcp-dist/omnireach-*.whl omnireach mcp
```

Send `initialize`, `notifications/initialized`, `tools/list`, and an
`omnireach_fetch` call for `https://example.com`. Expected: protocol version
`2025-06-18`, two tools, backend `http`, non-empty Markdown, and `isError: false`.

- [ ] **Step 5: Run real browser-backed MCP searches**

Record Chrome's visible window count:

```bash
osascript -e 'tell application "Google Chrome" to count windows'
```

Through one real `omnireach mcp` process, call:

```json
{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"omnireach_search","arguments":{"query":"Claude Code","sources":["reddit"],"limit":3}}}
{"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"omnireach_search","arguments":{"query":"Claude Code","sources":["xiaohongshu"],"limit":3}}}
```

Expected: both calls return real results, `errors` is empty, Reddit has numeric scores,
and localized Xiaohongshu likes are normalized to integers.

Record Chrome's visible window count again. Expected: unchanged from the starting count.

- [ ] **Step 6: Inspect final history and worktree**

Run: `git status --short`

Expected: only the implementation plan may remain uncommitted.

Run: `git log -6 --oneline`

Expected: separate commits exist for baseline fixes, service extraction, MCP server,
process test, plugin integration, and documentation.

- [ ] **Step 7: Commit the implementation plan**

```bash
git add docs/superpowers/plans/2026-07-10-agent-fast-path-mcp.md
git commit -m "docs: add MCP implementation plan"
```

Expected: clean worktree and all implementation commits ready for review.
