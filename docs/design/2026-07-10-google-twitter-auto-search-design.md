# Google and Twitter Auto Search Design

## Problem

`omnireach search "gpt5.6"` currently returns GitHub, Hacker News, YouTube, and
configured boosters, but it does not query Twitter/X. The Twitter adapter is healthy and
returns real results when selected explicitly; it is absent because `twitter` is excluded
from automatic routing.

Omnireach also has no Google source. Direct HTTP requests to Google Search return a
JavaScript challenge rather than a usable result page in the current environment. Google's
Custom Search JSON API is closed to new customers and is scheduled for discontinuation for
existing customers, so it cannot provide the install-and-run experience this project wants.
The installed OpenCLI Google command successfully returns real Google results through the
user's existing Chrome connection.

## Goals

- Make a normal `omnireach search <query>` include Google and Twitter results when OpenCLI
  is installed.
- Keep Chrome work silent by using the existing background, ephemeral, close-after-use
  OpenCLI bridge.
- Preserve explicit `--on` semantics: explicit sources are the complete source set.
- Preserve `--mode quick` as a lightweight path that does not invoke browser-backed sources.
- Keep Google and Twitter failures isolated so other source results are still returned.
- Ship with real end-to-end evidence from both upstreams, not only mocked fixtures.

## Non-Goals

- Reimplement a browser engine or Google DOM renderer inside Omnireach.
- Scrape Google's JavaScript challenge response with ad hoc string parsing.
- Add Google API keys, Programmable Search Engine IDs, or a paid search dependency.
- Automatically add other heavy sources such as Reddit, Xiaohongshu, TikTok, or Douyin.
- Change ranking beyond assigning Google a source trust value.

## Considered Approaches

### 1. OpenCLI-backed Google plus conditional automatic browser sources

Add a small Omnireach adapter around `opencli google search`. During non-explicit `auto`
and `deep` searches, append Google and Twitter when the `opencli` binary is present. Both
commands use the existing silent bridge flags.

This is the selected approach. It works against real Google and Twitter today, reuses the
user's established Chrome state, requires no new Python dependency, and matches the
project's existing login-walled adapter boundary.

### 2. Built-in HTTP Google scraper

Use `httpx` to request `google.com/search` and parse the returned HTML. This would avoid
OpenCLI, but the real response currently contains a JavaScript challenge and no usable SERP.
Shipping it would create a source that appears zero-config but fails under normal traffic.

### 3. Google Custom Search JSON API

Use the official JSON API. This would avoid Chrome, but new users cannot enroll, existing
access is being retired, and every installation would require credentials plus a search
engine identifier. It is incompatible with Omnireach's default-source experience.

## Architecture

### Google adapter

Add `omnireach.adapters.google.GoogleAdapter` following the existing Twitter adapter
pattern. It will:

- report ready when `opencli` is on `PATH`;
- call `run_opencli_json("google", "google", "search", query, "--limit", limit)`;
- rely on `run_opencli_json` to add `--window background`, `--site-session ephemeral`, and
  `--keep-tab false`;
- accept OpenCLI result objects with `type`, `title`, `url`, and `snippet`;
- discard non-result rows without an HTTP(S) URL, including People Also Ask rows;
- normalize standard and featured results into `SearchResult` objects with
  `source="google"`, `adapter="opencli"`, and `cost="free"`;
- preserve each complete upstream object in `raw`.

Register `google` as a `heavy` source with query hints `google`, `谷歌`, and `网页搜索`, a
15-second source timeout, and trust `0.85`. It remains `default_in_auto: false`; conditional
selection belongs in the application service rather than the static registry because users
without OpenCLI must not receive an unavailable Google error on every search.

### Automatic source augmentation

Extend the application service with a browser-source augmentation step after normal router
selection and before booster augmentation.

The step appends `google` and `twitter`, in that order, only when all of these conditions
hold:

- no explicit source list was supplied;
- mode is `auto` or `deep`;
- `opencli` is present on `PATH`;
- the source exists in the registry;
- the source is not already selected.

`quick` mode never adds them. Explicit `--on google`, `--on twitter`, or any other explicit
set remains exact. Like configured boosters, the optional sources may extend the router's
five-source base fanout rather than displacing a zero-configuration source.

OpenCLI presence is the cheap readiness gate. Authentication and bridge failures are left
to each adapter and become isolated `unavailable` source errors. Running `opencli doctor`
inside every search would add latency and duplicate the actual adapter call.

## Data Flow

1. CLI or MCP calls `omnireach.service.search`.
2. `Router` selects the existing hinted/default sources.
3. The service conditionally appends Google and Twitter for `auto` or `deep` mode.
4. The service appends configured paid boosters using the existing behavior.
5. `Dispatcher` runs every selected adapter concurrently with per-source timeouts.
6. Google and Twitter invoke OpenCLI in background ephemeral tabs and close them after use.
7. Results pass through the existing normalizer and scorer into the stable search envelope.

## Error Handling

- Missing OpenCLI: automatic augmentation skips both sources; explicit selection returns an
  actionable `AdapterUnavailable` error.
- Missing Chrome bridge or expired Twitter login: that source returns an isolated
  `unavailable` error while Google and all non-browser sources remain usable.
- Google CAPTCHA, empty SERP, or DOM drift: OpenCLI's command failure is surfaced as a
  Google source error rather than an empty success.
- Rows without valid result URLs are ignored. If every row is ignored, the adapter returns
  an empty list; OpenCLI itself is responsible for rejecting a completely empty extraction.
- Dispatcher cancellation continues to terminate the OpenCLI child process through the
  existing bridge implementation.

## Testing

### Automated tests

- Google adapter parses the real observed OpenCLI shape and preserves snippets/raw data.
- Google adapter skips PAA and malformed rows without HTTP(S) URLs.
- Google adapter uses the silent OpenCLI bridge and reports missing OpenCLI correctly.
- Registry includes `google`, with the expected tier, timeout, hints, and trust.
- Automatic service augmentation adds Google and Twitter when OpenCLI exists.
- Automatic service augmentation does not add them for `quick` mode, explicit sources, or
  an environment without OpenCLI.
- Existing router, dispatcher, CLI, MCP, registry, and adapter tests remain green.

Each behavior test is written and observed failing before production code is added.

### Real end-to-end verification

- Run `omnireach search --on google --limit 5 --json "gpt5.6"` and inspect the real field
  shape and result URLs.
- Run `omnireach search --on twitter --limit 5 --json "gpt5.6"` using the current logged-in
  Chrome profile.
- Run `omnireach search --json "gpt5.6"` and verify the envelope contains both `google` and
  `twitter` results.
- Measure visible Chrome window/tab counts before and after the automatic search and verify
  no visible tab remains open.
- Run the complete test suite and lint the changed Python files.

## Documentation

Update the English and Chinese READMEs, source table, command examples, and skill source
examples so users know that normal search automatically includes Google and connected
Twitter, while `quick` remains browser-free.
