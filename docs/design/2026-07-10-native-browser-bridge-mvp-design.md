# Native Browser Bridge MVP Design

## Goal

Prove that Omnireach can search a login-walled source through the user's existing Chrome
session without depending on the OpenCLI executable. The MVP migrates Douyin search only
and keeps OpenCLI as an automatic fallback for existing installations.

Success means this command returns real results while native mode is forced:

```bash
OMNIREACH_BROWSER_TRANSPORT=native omnireach search --on douyin --json "gpt5.6"
```

The command must reuse the user's current Douyin login, create no persistent visible tab or
window, leave no browser state behind, and work when `opencli` is absent from `PATH`.

## Scope

### Included

- An Omnireach-owned Manifest V3 Chrome extension.
- A dependency-free Python localhost bridge using the standard library.
- A transport selector with `auto`, `native`, and `opencli` modes.
- Native `douyin.search` implemented through stable rendered-DOM anchors.
- CLI commands to install the unpacked extension bundle and probe connectivity.
- Automatic OpenCLI fallback when native transport is not installed or not connected.
- Real end-to-end testing against the user's logged-in Chrome profile.

### Excluded

- Migrating Twitter, Xiaohongshu, Reddit, TikTok, Google, or WeChat in this release.
- Publishing the extension to the Chrome Web Store.
- Generic click/type/browser automation.
- Reading or decrypting Chrome's cookie database.
- Replaying Douyin's signed internal search API.
- Removing OpenCLI support from existing adapters.

## Strategy Note

Strategy: `UI_SELECTOR` / rendered DOM extraction

Contract: `visible-ui`

Evidence:

- observed state: `https://www.douyin.com/search/<query>?type=video` renders result cards
  under `[data-e2e="scroll-list"]`; each usable card contains an
  `a[href*="/video/"]` link;
- auth source: cookies and runtime state already held by the user's normal Chrome profile;
- replay result: direct synthesis of Douyin's internal search request is rejected by
  signature/security checks, while the rendered DOM contains non-empty real results;
- semantic anchors: `data-e2e="scroll-list"`, `/video/` URL shape, and visible login/security
  text;
- typed error path: login wall becomes unavailable/auth guidance; render timeout, malformed
  cards, and bridge protocol failures become execution failures.

The implementation does not copy OpenCLI's runtime or use its executable. It independently
uses the same externally visible page contract because that is the most stable source
available for Douyin search.

## Architecture

### 1. Browser transport boundary

Add `omnireach.browser_transport` with one operation:

```python
async def run_browser_json(
    source: str,
    command: str,
    *,
    payload: dict[str, object],
    opencli_args: tuple[str, ...],
) -> BrowserCommandResult
```

`BrowserCommandResult` contains normalized raw item dictionaries plus the transport label
used for `SearchResult.adapter`.

Transport mode comes from `OMNIREACH_BROWSER_TRANSPORT`:

- `auto` (default): use native for a supported configured source, otherwise OpenCLI;
- `native`: require the native bridge and never invoke OpenCLI;
- `opencli`: bypass native and retain current behavior.

In auto mode, missing native configuration or a disconnected extension falls back to
OpenCLI. A native command that reached the extension and failed during extraction does not
silently retry through OpenCLI, because that would duplicate site requests and hide native
parser regressions.

### 2. Native Python bridge

Add `omnireach.native_bridge`, implemented with `ThreadingHTTPServer` and no new package
dependency. Each browser command starts a short-lived server bound only to
`127.0.0.1:19826`.

Protocol:

- `GET /v1/job` returns the single pending job to the extension;
- `POST /v1/result` accepts the matching result envelope;
- every request requires `Authorization: Bearer <random-token>`;
- JSON request bodies are capped at 4 MiB;
- the server shuts down immediately after result, timeout, or cancellation;
- only one native browser command runs at a time; port contention is a typed unavailable
  error rather than selecting another random port the extension cannot know.

The token is generated once and stored at `~/.omnireach/bridge-token` with mode `0600`.
The same token is written into the installed unpacked extension's generated
`bridge-config.js`. Re-running install reuses the token so the extension does not require a
reload merely because the CLI was upgraded.

Result envelope:

```json
{"id":"...","ok":true,"items":[...]}
```

or:

```json
{"id":"...","ok":false,"error":{"kind":"auth|empty|runtime","message":"..."}}
```

Auth errors map to `AdapterUnavailable`. Runtime and protocol errors map to a native command
runtime exception and therefore dispatcher category `failed`.

### 3. Chrome extension

Package extension assets inside `omnireach/chrome_extension/` so wheels and sdists contain
them. `omnireach bridge install` copies the assets to
`~/.omnireach/chrome-extension`, writes `bridge-config.js`, and prints the exact directory
to load through Chrome's "Load unpacked" action.

Manifest permissions are limited to:

- `offscreen`, `scripting`, `storage`, `tabs`, and `windows`;
- `http://127.0.0.1:19826/*`;
- `https://www.douyin.com/*`.

The extension must not request `<all_urls>`, cookies permission, debugger permission, or
arbitrary browser-control access.

An offscreen document maintains a lightweight authenticated long-poll loop to the temporary
Python server. The service worker owns the command allowlist and browser operations. It
supports only:

- `system.ping`;
- `douyin.search`.

For Douyin search it creates a non-focused minimized temporary Chrome window, waits for the
page to finish loading, executes the allowlisted extraction function, and removes the window
in a `finally` block.

### 4. Douyin extraction

The injected function waits up to 15 seconds for one of four states:

- rendered cards under `[data-e2e="scroll-list"]`;
- a visible login/security wall;
- a visible empty-results message;
- timeout.

Each card is serialized as its video link plus ordered leaf text nodes. Extension-side pure
projection logic then derives:

- canonical `https://www.douyin.com/video/<numeric-id>` URL;
- description from the longest non-metadata leaf text;
- author from the leaf following `@`;
- likes from a numeric leaf supporting plain, `万`, and `亿` forms;
- plays/comments/shares as zero because the search card does not expose them.

Rows without both canonical URL and description cause a runtime parser error rather than
being silently dropped.

### 5. CLI and readiness

Add:

```bash
omnireach bridge install
omnireach bridge status --json
omnireach bridge path
```

`bridge status` sends `system.ping` through the real native bridge. It distinguishes assets
installed from extension connected.

`DouyinAdapter.is_ready` returns true when either native configuration exists or OpenCLI is
installed. Its search method delegates to the browser transport and records
`adapter="native-chrome"` or `adapter="opencli"` according to the actual path.

Douyin setup no longer automatically installs OpenCLI. Its setup guidance installs the
native extension first and documents OpenCLI as fallback.

## Security

- Bind only to IPv4 loopback.
- Require a 256-bit-equivalent random bearer token on every request.
- Use a fixed allowlist for command and domain inside the extension.
- Reject unknown job fields and result IDs.
- Cap input sizes and timeouts.
- Never expose arbitrary JavaScript evaluation through the protocol.
- Close temporary windows in `finally`, including extraction errors.
- Do not persist page content, cookies, or result payloads.

The local token protects against drive-by webpages and unrelated local callers. It does not
claim to defend against another process running as the same local user that can read the
token file; this matches the existing local CLI threat model.

## Testing

### Python automated tests

- Extension install is idempotent, preserves token, writes `0600`, and copies all assets.
- Bridge rejects missing/wrong token, oversized bodies, unknown result IDs, and malformed
  envelopes.
- A simulated extension can poll a job and post a result through the real HTTP server.
- Timeout and port contention produce typed unavailable errors.
- Transport mode selection and OpenCLI fallback are deterministic.
- Forced native mode never calls OpenCLI.
- Douyin adapter preserves current normalized field behavior and reports the actual adapter.
- Manifest validation rejects broad permissions and confirms required allowlists.

### JavaScript checks

- Pure count parsing, URL normalization, card projection, and malformed-card rejection run
  under Node's built-in test runner without adding a Node dependency to Omnireach runtime.
- Static checks confirm the service worker command/domain allowlist and `finally` cleanup.

### Real end-to-end

1. Run `omnireach bridge install`.
2. Load the generated unpacked extension into the user's existing Chrome profile.
3. Verify `omnireach bridge status --json` reports connected.
4. Record visible Chrome window/tab counts.
5. Run forced native Douyin search with OpenCLI bypassed.
6. Verify real result fields and `adapter="native-chrome"`.
7. Verify visible Chrome window/tab counts return to the baseline and no temporary window
   remains.
8. Run the same search in auto mode and confirm native is selected.
9. Disable native configuration in a test HOME and verify auto mode falls back to OpenCLI.

## Release

Ship as `0.14.0-alpha`. This is a new capability, not a patch-level behavior correction.
OpenCLI remains required for non-migrated browser-backed sources.
