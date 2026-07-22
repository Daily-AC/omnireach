---
name: omnireach
description: This skill should be used to call `omnireach_search`, `omnireach_fetch`, or `omnireach_parse_media` when the user asks to search the web, read a URL, parse video/audio metadata or captions, or avoid browser automation for read-only web work.
---

# omnireach

Use omnireach as the read-only web fast path. Search across ordinary web sources and
login-walled vertical platforms, then fetch full page Markdown through one stable schema.
Keep browser automation for interactions that search and fetch cannot perform.

## Tool Choice Policy

1. Call `omnireach_search` first for web research or platform search.
2. Call `omnireach_fetch` first to read an HTTP or HTTPS URL.
3. Call `omnireach_parse_media` first for video/audio metadata or captions.
4. Use the omnireach CLI fallback only when these MCP tools are unavailable.
5. Use Playwright or browser control only for clicks, forms, uploads, downloads,
   screenshots, visual inspection, or unsupported interactive workflows.

Do not launch Playwright merely to search or extract readable page content.

## Search

Call `omnireach_search` with a non-empty `query`.

Optional arguments:

- `sources`: restrict the call to source IDs such as `google`, `twitter`, `reddit`,
  `xiaohongshu`, `wechat`, `hackernews`, or `bilibili`.
- `mode`: use `auto`, `quick`, or `deep`; explicit `sources` take precedence.
- `limit`: request 1 through 50 results per source.
- `timeout`: optional 1 through 120 second override. When omitted, browser-backed heavy
  sources use their 60 second cold-start-safe default.
- `profile`: select an OpenCLI Browser Bridge profile when more than one Chrome profile is
  connected.

Read `results` as normalized search metadata. Treat each result's `content` as a snippet,
not the full document. Inspect `errors` for unavailable or failed sources while retaining
successful results from other sources.

Google, Reddit, Twitter, Xiaohongshu, TikTok, and Douyin prefer the Omnireach native Chrome
bridge when it is installed, and fall back to OpenCLI only when that bridge is unavailable.
Use `quick` when the search must remain browser-free. An explicit `sources` list is exact
and disables automatic additions. The experimental `agy` source is explicit-only and
requires a configured dedicated conversation.

Use `omnireach_fetch` on a selected result URL when full text is required. Treat an empty
`content_markdown` plus `errors` as a failed fetch. Omnireach rejects known verification and
login-wall placeholders, including short Reddit verification pages.

## Fetch

Call `omnireach_fetch` with an absolute HTTP or HTTPS `url`.

Leave `backend` as `auto` unless diagnosing a backend. Auto routing uses built-in HTTP then
Jina for ordinary pages and the logged-in OpenCLI Chrome bridge for supported WeChat URLs.
Ordinary HTTP fetch does not start Chrome. Browser-backed paths use a hidden ephemeral tab
and close it after the call.

Treat `content_markdown` as successful only when it is non-empty. Inspect `errors` for
blocked requests, CAPTCHA detection, unavailable backends, and fallback attempts. A tool
result marked as an error still contains the full fetch envelope for recovery.

## Media

Call `omnireach_parse_media` with an absolute HTTP or HTTPS `url`. Use `mode=inspect` when
only metadata and available subtitle languages are needed; inspect does not write files.
Use `mode=quick` to materialize metadata, the selected caption track, transcript JSON and
Markdown, and a manifest. Quick mode does not download the full video.

Set `language` when a specific caption language is required. For a direct media URL, pass a
public `subtitle_url` for a sidecar VTT, SRT, JSON3, or Bilibili BCC file. Long transcripts
live in the absolute paths under `artifacts`; `transcript.text_preview` is intentionally
bounded. Treat `ok=false` as failure and inspect structured `errors`; transient TLS and
network failures are marked `retryable=true`.

Bilibili reports when captions require login. Only then, and only with explicit user
authorization, set `cookies_from_browser` to a yt-dlp browser spec such as
`chrome:Profile 1`. Omit it by default. The browser spec and cookies never appear in the
envelope or artifacts. Quick parse reuses a cache entry only after checking every artifact's
size and SHA-256; set `reuse_cache=false` to force a fresh parse. Use `max_duration` to reject
media longer than the requested number of seconds.

## Setup and Recovery

If the MCP tools are absent but `omnireach` is installed, use the CLI fallback documented
in `references/cli.md`.

If the CLI is absent, install it with the idempotent installer:

```bash
curl -fsSL https://raw.githubusercontent.com/Daily-AC/omnireach/main/install.sh | sh
```

Do not invoke interactive `omnireach setup <source>` from an unattended agent process.
For browser-backed search sources, run `omnireach bridge install`, ask the user to load the
printed directory once as an unpacked Chrome extension, then check `omnireach bridge status
--json`. OpenCLI remains an optional compatibility fallback. For agy grounded search, run
`omnireach agy configure <conversation-id>` and verify `omnireach agy status --json`.

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
