---
name: omnireach
description: This skill should be used to call `omnireach_search` or `omnireach_fetch` when the user asks to "search the web", "research a topic", "search Google, Twitter, Reddit, 小红书, 微信公众号, 抖音, B站, TikTok, YouTube, HackerNews, GitHub, or RSS", "read this URL", "fetch this article", or "avoid Playwright/browser automation" for read-only web work. It provides MCP-first search and fetch through the user's existing Chrome login state when required.
---

# omnireach

Use omnireach as the read-only web fast path. Search across ordinary web sources and
login-walled vertical platforms, then fetch full page Markdown through one stable schema.
Keep browser automation for interactions that search and fetch cannot perform.

## Tool Choice Policy

1. Call `omnireach_search` first for web research or platform search.
2. Call `omnireach_fetch` first to read an HTTP or HTTPS URL.
3. Use the omnireach CLI fallback only when these MCP tools are unavailable.
4. Use Playwright or browser control only for clicks, forms, uploads, downloads,
   screenshots, visual inspection, or unsupported interactive workflows.

Do not launch Playwright merely to search or extract readable page content.

## Search

Call `omnireach_search` with a non-empty `query`.

Optional arguments:

- `sources`: restrict the call to source IDs such as `google`, `twitter`, `reddit`,
  `xiaohongshu`, `wechat`, `hackernews`, or `bilibili`.
- `mode`: use `auto`, `quick`, or `deep`; explicit `sources` take precedence.
- `limit`: request 1 through 50 results per source.
- `timeout`: allow 1 through 120 seconds.

Read `results` as normalized search metadata. Treat each result's `content` as a snippet,
not the full document. Inspect `errors` for unavailable or failed sources while retaining
successful results from other sources.

Douyin search prefers the Omnireach native Chrome bridge when it is installed, and falls
back to OpenCLI only when that bridge is unavailable. Google and Twitter still use OpenCLI
through hidden ephemeral Chrome tabs. Use `quick` when the search must remain browser-free.
An explicit `sources` list is exact and disables automatic additions.

Use `omnireach_fetch` on a selected result URL when full text is required.

## Fetch

Call `omnireach_fetch` with an absolute HTTP or HTTPS `url`.

Leave `backend` as `auto` unless diagnosing a backend. Auto routing uses built-in HTTP then
Jina for ordinary pages and the logged-in OpenCLI Chrome bridge for supported WeChat URLs.
Ordinary HTTP fetch does not start Chrome. Browser-backed paths use a hidden ephemeral tab
and close it after the call.

Treat `content_markdown` as successful only when it is non-empty. Inspect `errors` for
blocked requests, CAPTCHA detection, unavailable backends, and fallback attempts. A tool
result marked as an error still contains the full fetch envelope for recovery.

## Setup and Recovery

If the MCP tools are absent but `omnireach` is installed, use the CLI fallback documented
in `references/cli.md`.

If the CLI is absent, install it with the idempotent installer:

```bash
curl -fsSL https://raw.githubusercontent.com/Daily-AC/omnireach/main/install.sh | sh
```

Do not invoke interactive `omnireach setup <source>` from an unattended agent process.
For Douyin, run `omnireach bridge install`, ask the user to load the printed directory once
as an unpacked Chrome extension, then check `omnireach bridge status --json`. Other
login-backed sources may still require OpenCLI and its Chrome extension.

Run `omnireach doctor --json` to diagnose source readiness and backend support. Prefer a
different configured source or ordinary HTTP fallback when a nonessential source is
unavailable.

## Boundary

Use omnireach for finding and reading information. Do not claim it replaces full browser
automation. Switch to browser control only when the requested outcome requires page state
changes, visual evidence, or an interaction sequence.

## Additional Resources

- Read `references/cli.md` for CLI fallback commands, JSON envelopes, backend flags, and
  MCP client registration.
