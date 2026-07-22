# omnireach CLI Fallback Reference

Use this reference only when the omnireach search, fetch, and media MCP tools are not
available or when diagnosing the installed CLI.

## Machine-Readable Output

Always request JSON explicitly from an agent terminal:

```bash
omnireach search --json "Claude Code"
omnireach fetch --json "https://example.com/article"
omnireach media inspect --json "https://www.youtube.com/watch?v=<id>"
omnireach media parse --language en --json "https://www.youtube.com/watch?v=<id>"
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

With the native bridge or OpenCLI installed, normal and deep searches automatically include
Google and Twitter through background ephemeral Chrome tabs. `--mode quick` stays
browser-free. `--on` is exact and does not add either source unless requested. `--sources`
is an alias for `--on`, matching the MCP argument name.

Restrict sources:

```bash
omnireach search --on reddit,xiaohongshu --limit 5 --json "Claude Code"
omnireach search --on wechat --json "AI 编程"
omnireach search --sources reddit --profile work --timeout 90 --json "Claude Code"
```

Set up the native browser bridge once:

```bash
omnireach bridge install
omnireach bridge path
omnireach bridge status --json
OMNIREACH_BROWSER_TRANSPORT=native omnireach search --on google,twitter --json "AI 编程"
```

Load the directory printed by `bridge install` once as an unpacked Chrome extension.
Transport modes are `auto` (native first, OpenCLI fallback), `native` (never call OpenCLI),
and `opencli` (force the compatibility path).

Configure the experimental agy grounded-search backend with a dedicated conversation:

```bash
omnireach agy configure <conversation-id>
omnireach agy status --json
omnireach search --on agy --json "Python free threading"
```

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

Browser-backed heavy sources default to 60 seconds for cold starts. An explicit `--timeout`
overrides every selected source. Use `--profile <name>` when `omnireach doctor --json` reports
multiple connected OpenCLI Browser Bridge profiles.

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
Known verification and login-wall placeholders are recorded in `errors` and never returned as
successful content. Reddit verification errors suggest `opencli reddit read <url> --format md`
as a logged-in fallback.

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

The server exposes `omnireach_search`, `omnireach_fetch`, and `omnireach_parse_media` and writes only MCP JSON-RPC
messages to stdout.

## Media

`media inspect` returns metadata and subtitle tracks without writing files. `media parse`
uses upstream captions when available and writes normalized artifacts under
`~/.cache/omnireach/media/` by default. Override this with `--output-dir`. Direct media can
use `--subtitle-url <url>` for a sidecar VTT, SRT, JSON3, or Bilibili BCC subtitle.

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

Google, Reddit, Twitter, Xiaohongshu, TikTok, and Douyin prefer the Omnireach native Chrome
bridge. OpenCLI remains the compatibility fallback and receives `--window background
--site-session ephemeral --keep-tab false`; direct calls to old OpenCLI versions may still
create visible tabs.
