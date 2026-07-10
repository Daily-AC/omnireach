# omnireach CLI Fallback Reference

Use this reference only when the `omnireach_search` and `omnireach_fetch` MCP tools are not
available or when diagnosing the installed CLI.

## Machine-Readable Output

Always request JSON explicitly from an agent terminal:

```bash
omnireach search --json "Claude Code"
omnireach fetch --json "https://example.com/article"
```

Alternatively, force JSON for the entire harness:

```bash
export OMNIREACH_FORCE_JSON=1
```

## Search

Run a routed search:

```bash
omnireach search --json "Claude Code prompt caching"
```

With OpenCLI installed, normal and deep searches automatically include Google and Twitter
through hidden ephemeral Chrome tabs. `--mode quick` stays browser-free. `--on` is exact and
does not add either source unless requested.

Restrict sources:

```bash
omnireach search --on reddit,xiaohongshu --limit 5 --json "Claude Code"
omnireach search --on wechat --json "AI 编程"
```

Set up the native Douyin bridge once:

```bash
omnireach bridge install
omnireach bridge path
omnireach bridge status --json
OMNIREACH_BROWSER_TRANSPORT=native omnireach search --on douyin --json "AI 编程"
```

Load the directory printed by `bridge install` once as an unpacked Chrome extension.
Transport modes are `auto` (native first, OpenCLI fallback), `native` (never call OpenCLI),
and `opencli` (force the compatibility path).

The search envelope contains:

```json
{
  "query": "...",
  "ts": "ISO 8601 Z",
  "results": [
    {
      "source": "reddit",
      "adapter": "opencli",
      "title": "...",
      "url": "https://...",
      "content": "search snippet",
      "author": "...",
      "ts": "ISO 8601 or null",
      "score": 0.0,
      "engagement": {},
      "raw": {},
      "cost": "free"
    }
  ],
  "errors": [
    {"source": "...", "error": "...", "category": "unavailable"}
  ]
}
```

Fetch a result URL to obtain full content; search `content` is intentionally capped as a
snippet.

## Fetch

Use host-aware automatic routing:

```bash
omnireach fetch --json "https://example.com/article"
omnireach fetch --json "https://mp.weixin.qq.com/s/example"
```

The fetch envelope contains:

```json
{
  "url": "https://...",
  "backend": "http",
  "fetched_at": "ISO 8601 Z",
  "content_markdown": "# Title\n\nBody",
  "errors": []
}
```

Backend behavior:

- `auto`: use OpenCLI for supported WeChat URLs; otherwise try built-in HTTP then Jina.
- `http`: use browserless HTTP and local HTML-to-Markdown extraction.
- `jina`: force Jina Reader.
- `opencli`: force the WeChat login-state path.
- `crwl`: explicitly opt into an installed Crawl4AI backend.

Use `--backend <name>` only for diagnosis or an explicit user request. Fetch exits nonzero
when every backend fails, even though it still prints the JSON envelope.

## MCP Server Command

Start the dependency-free stdio server with:

```bash
omnireach mcp
```

Use this standard MCP configuration in clients that do not install the omnireach plugin:

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

The server exposes `omnireach_search` and `omnireach_fetch` and writes only MCP JSON-RPC
messages to stdout.

## Diagnosis

Inspect readiness:

```bash
omnireach doctor --json
omnireach sources --probe --json
```

Run interactive setup only in a user-controlled terminal:

```bash
omnireach setup reddit
omnireach setup xiaohongshu
omnireach setup twitter
omnireach setup google
```

Douyin prefers the Omnireach native Chrome bridge. Other login-backed adapters still
require OpenCLI and its Chrome extension while they migrate. OpenCLI calls pass `--window
background --site-session ephemeral --keep-tab false`; direct calls to old OpenCLI versions
may still create visible tabs.
