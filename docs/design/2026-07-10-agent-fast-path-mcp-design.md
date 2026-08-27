# Agent Fast Path MCP Design

Date: 2026-07-10
Status: Approved for implementation planning

## Context

Agents frequently launch Playwright for tasks that only require searching or reading a
page. That path is slow, consumes substantial resources, and may surface visible Chrome
tabs. Omnireach already provides the required read-only primitives through its CLI, but
agents do not discover arbitrary CLI commands as reliably as model-controlled MCP tools.

The current CLI also keeps orchestration inside Click command handlers. Adding an MCP
server by spawning `omnireach search --json` and `omnireach fetch --json` would duplicate
process management and make cancellation and errors harder to reason about.

## Goals

- Expose search and fetch as standard, model-controlled MCP tools.
- Make omnireach the default fast path for agent search and page reading.
- Keep Playwright as a fallback for interaction and visual verification only.
- Preserve the current CLI and JSON contracts.
- Add no runtime dependencies to the base wheel.
- Preserve silent Chrome behavior for login-backed sources.
- Return partial source failures in a form the model can inspect and recover from.

## Non-Goals

- Replace Playwright for clicking, form submission, uploads, downloads, screenshots,
  visual regression, or arbitrary browser workflows.
- Add Streamable HTTP transport, authentication, prompts, resources, or MCP sampling.
- Vendor the OpenCLI framework or implement a generic browser-control tool.
- Automatically install software when an MCP process starts.
- Change source ranking or fetch backend selection.

## Options Considered

### Official Python MCP SDK

This minimizes protocol code but adds a new dependency tree and makes a small read-only
server depend on framework lifecycle behavior. It conflicts with the repository's current
dependency reduction goal.

### Skill and CLI only

This adds no protocol code, but tool discovery remains unreliable. Agents can still prefer
an already-visible Playwright tool over a command documented inside a skill.

### Minimal stdio MCP server

Implement the stable subset used by this project directly: initialization, ping,
`tools/list`, and `tools/call`. MCP stdio is newline-delimited UTF-8 JSON-RPC, so this
requires little code and no new package. This is the selected approach.

## Architecture

### Application Service Layer

Add `omnireach/service.py` as the reusable boundary between transports and domain logic.
It owns no terminal rendering.

Expose two functions:

```python
async def search(
    query: str,
    *,
    sources: list[str] | None = None,
    mode: str = "auto",
    limit: int = 10,
    timeout: float = 30.0,
) -> SearchEnvelope: ...

def fetch(
    url: str,
    *,
    backend: str = "auto",
    timeout: float = 30.0,
) -> FetchEnvelope: ...
```

Move routing, adapter loading, dispatch, ranking, and envelope construction out of the
Click search handler. Move fetch backend iteration and envelope construction out of the
Click fetch handler. Keep backend implementations in `commands/fetch.py` unless moving
them produces a clearer module boundary during implementation.

Add `FetchEnvelope` to `omnireach/contract.py` so CLI and MCP serialize the same typed
result. Preserve the existing JSON field names:

- `url`
- `backend`
- `fetched_at`
- `content_markdown`
- `errors`

The Click handlers become rendering adapters. They validate CLI syntax, call the service,
emit JSON or Rich output, and retain current exit-code behavior.

### MCP Server

Add `omnireach/mcp_server.py` and register `omnireach mcp` as a Click subcommand. The
server reads one JSON-RPC message per line from stdin and writes exactly one JSON-RPC
message per line to stdout when a response is required. Diagnostics go to stderr only.

Implement MCP protocol version `2025-06-18` with these methods:

- `initialize`
- `notifications/initialized`
- `ping`
- `tools/list`
- `tools/call`

Return standard JSON-RPC errors for malformed JSON, invalid requests, unknown methods,
unknown tools, and invalid arguments. Return tool execution failures inside a tool result
with `isError: true`, as required by the MCP tools specification.

Advertise only the `tools` server capability. Set `listChanged` to `false` because the
tool set is static for the lifetime of the process.

### Tool Definitions

Expose `omnireach_search` with this input:

- `query`: required non-empty string
- `sources`: optional array of source IDs
- `mode`: optional `auto`, `quick`, or `deep`; default `auto`
- `limit`: optional integer from 1 through 50; default 10
- `timeout`: optional number from 1 through 120 seconds; default 30

When `sources` is present, it is authoritative and `mode` does not add sources. Reject an
unknown source ID as invalid tool arguments instead of silently skipping it.

Return the existing `SearchEnvelope` as `structuredContent`. Also return the same object as
compact JSON in a text content block for clients that do not consume structured content.
Source-level failures remain in `errors`; successful results from other sources are not
discarded and do not set `isError`.

Expose `omnireach_fetch` with this input:

- `url`: required absolute HTTP or HTTPS URL
- `backend`: optional `auto`, `http`, `jina`, `crwl`, or `opencli`; default `auto`
- `timeout`: optional number from 1 through 120 seconds; default 30

Return `FetchEnvelope` in both structured and text forms. Set `isError: true` only when no
content backend succeeds. Preserve the attempted backend errors in the envelope so the
model can choose another path.

Mark both tools read-only, non-destructive, and idempotent in MCP annotations. Network and
browser activity must be stated in their descriptions. The search description must say
that login-backed sources may use the user's Chrome session through a hidden ephemeral tab.

### Plugin Registration

Add `.mcp.json` at the repository/plugin root, as a sibling of the `.claude-plugin`
directory:

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

The installer already installs the CLI before registering the skill, so it satisfies the
command prerequisite. Starting the MCP server must never bootstrap or update packages.
Document the same command for non-plugin MCP clients.

### Agent Routing Skill

Revise the plugin skill around a short tool-choice policy:

1. Use `omnireach_search` for web research and platform search.
2. Use `omnireach_fetch` to read an HTTP or HTTPS URL.
3. Fall back to the omnireach CLI only when the MCP tools are unavailable.
4. Use Playwright or another browser-control tool only when the task requires interaction,
   file transfer, screenshots, visual inspection, or an unsupported dynamic workflow.

Make these triggers explicit in frontmatter: web research, searching a platform, reading a
URL, fetching an article, and avoiding browser automation. Keep operational CLI details in
a reference file so the loaded skill remains concise.

Do not claim that omnireach replaces full browser automation. Describe it as the preferred
read-only search and fetch path.

## Data Flow

For search:

1. MCP client calls `omnireach_search`.
2. MCP validates arguments.
3. Service plans sources, loads adapters, and dispatches concurrently.
4. Existing adapters use HTTP or the silent OpenCLI bridge as appropriate.
5. Service ranks results and returns `SearchEnvelope`.
6. MCP emits structured and text representations.

For fetch:

1. MCP client calls `omnireach_fetch`.
2. MCP validates the URL and options.
3. Service selects the existing host-aware backend sequence.
4. Ordinary pages use built-in HTTP then Jina; WeChat uses the silent OpenCLI path.
5. Service returns `FetchEnvelope`, including failed attempts.
6. MCP sets `isError` according to whether content was obtained.

## Error Semantics

- JSON parse failure: JSON-RPC `-32700`.
- Invalid JSON-RPC request: `-32600`.
- Unknown method or tool: `-32601`.
- Invalid tool arguments: `-32602`.
- Unexpected server failure: JSON-RPC `-32603`, with no traceback on stdout.
- Expected search adapter failures: successful tool result with `errors` populated.
- Fetch exhaustion: tool result with the full envelope and `isError: true`.
- Cancellation or stdin closure: stop accepting work and terminate without extra stdout.

## Testing

Follow test-driven development for each production boundary.

### Unit and Contract Tests

- Service search produces the same envelope as the current CLI behavior.
- Service fetch preserves backend order, CAPTCHA handling, and errors.
- CLI JSON output remains contract-compatible after extraction.
- MCP initialization negotiates the declared version and capabilities.
- MCP `tools/list` returns two schemas and read-only annotations.
- MCP tool calls return matching `structuredContent` and text JSON.
- Invalid arguments and unknown tools return the specified error classes.
- Notifications produce no stdout response.
- Logs and tracebacks never contaminate stdout.
- Plugin `.mcp.json` parses and points to `omnireach mcp`.
- Skill text encodes MCP-first and Playwright-last routing.

### Process-Level MCP Test

Launch `omnireach mcp` as a subprocess and exchange real newline-delimited JSON-RPC:

1. `initialize`
2. `notifications/initialized`
3. `tools/list`
4. `tools/call`

Verify process shutdown by closing stdin. This test must exercise the installed entry point
from a built wheel, not only a direct module import.

### Real End-to-End Verification

- Call `omnireach_search` through MCP against Reddit.
- Call `omnireach_search` through MCP against the logged-in Xiaohongshu session.
- Call `omnireach_fetch` through MCP against an ordinary public page.
- Confirm results have real upstream field shapes and no tool errors.
- Record visible Chrome window counts before and after browser-backed calls; both counts
  must remain unchanged.
- Build wheel and sdist, inspect wheel metadata, and confirm no MCP SDK or Playwright
  dependency was added.

## Compatibility and Rollout

- Keep all existing CLI commands and options.
- Keep the CLI as the fallback documented by the skill.
- Do not enable browser-backed sources in automatic fanout solely because MCP exists.
- Ship MCP as an additive interface in the current alpha version.
- Document client registration and the precise boundary where Playwright remains necessary.

## Completion Criteria

Implementation is complete when:

- A compatible MCP client discovers and calls both tools through stdio.
- CLI and MCP return the same domain envelopes for equivalent inputs.
- The plugin registers the MCP server automatically when the CLI is installed.
- The skill directs read-only web work to MCP before Playwright.
- Unit, full-suite, package, protocol, and real upstream tests pass.
- Browser-backed MCP calls leave no visible Chrome window or tab behind.
- The base wheel contains no new runtime dependency.
