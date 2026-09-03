---
name: omnireach
description: This skill should be used to call `omnireach_search`, `omnireach_author`, `omnireach_fetch`, `omnireach_parse_media`, or `omnireach_download_media` when the user asks to search the web, list what one creator posted, read a URL, parse video/audio metadata or captions, download a Douyin video, or avoid browser automation for supported web work.
---

# omnireach

Use omnireach as the supported web and media fast path. Search across ordinary web sources
and login-walled vertical platforms, fetch full page Markdown, parse media, or download a
bounded Douyin MP4 through stable schemas. Keep browser automation for unsupported actions.

## Tool Choice Policy

1. Call `omnireach_search` first for web research or platform search.
2. Call `omnireach_author` when the question is what one named creator posted, rather than
   what was posted about them.
3. Call `omnireach_fetch` first to read an HTTP or HTTPS URL.
4. Call `omnireach_parse_media` first for video/audio metadata or captions.
5. Call `omnireach_download_media` for an explicitly requested Douyin video download.
6. Use the omnireach CLI fallback only when these MCP tools are unavailable.
7. Use Playwright or browser control only for clicks, forms, uploads, unsupported downloads,
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

## Creator Catalog

Call `omnireach_author` with a `handle` when the user names a creator and wants that
creator's own works. `omnireach_search` answers a different question — it matches captions,
so a creator's name returns mostly other accounts' fan edits, reaction videos, and clips
that merely `@` them, and ranking those by likes puts a stranger at the top.

`source` is `douyin` today. Optional arguments:

- `limit`: 1 through 200 works, default 20.
- `order`: `recent` or `likes`. `recent` is true newest-first: Douyin hoists pinned works to
  the front of its own response, and each result carries `raw.pinned` so a pinned older video
  is visible for what it is instead of reading as the newest. `likes` has to page the entire
  catalog before it can rank, so it is the slow path — raise `timeout` and check `complete`
  before trusting the top of the list.
- `include_media_urls`: attach the expiring signed CDN playback URL to each result's `raw`.
  Off by default. Turn it on only when the user is going to download the files, and treat
  the URLs as valid for minutes, not hours.
- `timeout`: 5 through 600 seconds, default 180. A ~355-work catalog paged in about 40
  seconds when measured.

Read `author` to confirm which account was resolved. A bare nickname is resolved by follower
count because impersonator accounts copy nicknames exactly; when the user needs certainty,
pass the profile URL instead and `author.resolved_from` will read `url`. `scanned` reports
how many works were paged and `complete` reports whether paging reached the end.

Engagement counters on catalog results are exact, unlike keyword-search results. `views` is
always absent because the endpoint no longer reports play counts.

Do not classify content from this metadata. On a measured 355-work sample only 9 captions
contained the topic word at all, and the platform's own `video_tag` taxonomy labelled just 2
of them correctly, so filtering by caption or tag silently discards most matches.

The creator catalog needs the native Chrome bridge. If the tool reports that the connected
extension does not implement `douyin.author`, run `omnireach bridge install` and ask the
user to reload the unpacked extension at `chrome://extensions`.

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
`chrome:Profile 1`. Omit it by default — the user may already have authorized a default
profile through `[media] cookies_from_browser` in `~/.omnireach/preferences.toml`, which
applies whenever the call omits the argument. The browser spec and cookies never appear in the
envelope or artifacts. Quick parse reuses a cache entry only after checking every artifact's
size and SHA-256; set `reuse_cache=false` to force a fresh parse. Use `max_duration` to reject
media longer than the requested number of seconds.

Call `omnireach_download_media` only when the user explicitly requests a Douyin download.
It writes one combined MP4 into an OmniReach-managed directory and returns a `media`
artifact with an absolute path, byte count, and SHA-256. `quality=compatible` prefers H.264;
`best` maximizes resolution/bitrate and `small` minimizes bytes. Keep `max_size_mb` bounded.
Douyin currently requires fresh cookies, so set `cookies_from_browser` only with explicit
user authorization. Douyin also answers a verification challenge at random; omnireach
already retries that automatically, so a returned `retryable=true` error means the whole
retry budget was spent — wait before repeating the call rather than looping on it. MCP does not accept an arbitrary output directory. Cached files are
reused only after size and SHA-256 verification.

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

Use omnireach for finding and reading information, parsing media, and bounded Douyin
downloads. Do not claim it replaces full browser automation. Switch to browser control only
when the requested outcome requires page state changes, visual evidence, or an unsupported
interaction sequence.

## Additional Resources

- Read `references/cli.md` for CLI fallback commands, JSON envelopes, backend flags, and
  MCP client registration.
