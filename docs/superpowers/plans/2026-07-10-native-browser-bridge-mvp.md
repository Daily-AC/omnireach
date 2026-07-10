# Native Browser Bridge MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Douyin search work through an Omnireach-owned Chrome extension and dependency-free Python bridge without invoking the OpenCLI executable.

**Architecture:** A packaged MV3 extension long-polls a short-lived authenticated localhost HTTP server. A transport selector prefers native for supported configured commands and falls back to the existing OpenCLI bridge when native is absent or disconnected.

**Tech Stack:** Python stdlib HTTP/threading/importlib.resources, asyncio, Click, Chrome Manifest V3 extension APIs, plain JavaScript, Node built-in test runner, pytest.

---

### Task 1: Extension Asset Installer and CLI Surface

**Files:**
- Create: `omnireach/bridge_install.py`
- Create: `omnireach/chrome_extension/__init__.py`
- Create: `omnireach/chrome_extension/manifest.json`
- Create: `omnireach/chrome_extension/offscreen.html`
- Create: `omnireach/chrome_extension/bridge-config.example.js`
- Create: `omnireach/commands/bridge.py`
- Modify: `omnireach/cli.py`
- Test: `tests/test_bridge_install.py`
- Test: `tests/test_cmd_bridge.py`
- Test: `tests/test_extension_manifest.py`

- [ ] Write failing tests requiring idempotent token generation, `0600` token permissions,
  copied packaged assets, generated `bridge-config.js`, stable install path, safe manifest
  permissions, and `bridge install/path` JSON output.
- [ ] Run the focused tests and verify failures are caused by missing modules/commands.
- [ ] Implement `BridgePaths`, `bridge_paths(home=None)`, `install_extension(home=None)`,
  `bridge_configured(home=None)`, and the Click `bridge` group with `install`, `status`, and
  `path` subcommands. `status` may initially report configured only; Task 2 replaces it with
  a real ping.
- [ ] Register `bridge_cmd` in `omnireach.cli`.
- [ ] Run focused tests and commit `feat: add native bridge installer`.

Required manifest invariants:

```json
{
  "manifest_version": 3,
  "permissions": ["offscreen", "scripting", "tabs", "windows"],
  "host_permissions": [
    "http://127.0.0.1:19826/*",
    "https://www.douyin.com/*"
  ]
}
```

Tests must reject `<all_urls>`, `cookies`, and `debugger`.

### Task 2: Authenticated Native HTTP Bridge

**Files:**
- Create: `omnireach/native_bridge.py`
- Modify: `omnireach/commands/bridge.py`
- Test: `tests/test_native_bridge.py`
- Modify: `tests/test_cmd_bridge.py`

- [ ] Write failing tests using a simulated extension client against a real loopback server.
  Cover authenticated job polling/result posting, wrong token, malformed JSON, oversized
  body, wrong result ID, connection timeout, result timeout, cancellation, and port
  contention.
- [ ] Verify RED.
- [ ] Implement `NativeBridgeUnavailable`, `NativeBridgeCommandError`, `BridgeJob`, and a
  short-lived `ThreadingHTTPServer` bound to `127.0.0.1:19826`.
- [ ] Implement `run_native_job(command, payload, *, home=None, port=19826,
  connect_timeout=2.0, result_timeout=22.0, cancel_event=None)`.
- [ ] Validate result envelopes and map `auth` to unavailable while `runtime`/protocol errors
  raise `NativeBridgeCommandError`.
- [ ] Make `bridge status` send a real `system.ping` job and expose installed/connected/error
  fields in JSON.
- [ ] Run focused tests and commit `feat: add authenticated native bridge protocol`.

### Task 3: Douyin Pure Projection Logic

**Files:**
- Create: `omnireach/chrome_extension/douyin.js`
- Create: `tests/js/native-extension.test.mjs`
- Create: `tests/test_extension_js.py`

- [ ] Write Node tests first for `parseCount`, canonical numeric Douyin video URLs, author
  extraction, metadata filtering, longest-description selection, limit validation, and
  malformed-card rejection.
- [ ] Run through the pytest wrapper and verify RED because `douyin.js` is absent.
- [ ] Implement a classic-script global `globalThis.OmnireachDouyin` with pure projection
  functions. Do not depend on DOM or Node modules.
- [ ] Run Node/pytest tests and reverse-validate by temporarily making URL normalization
  accept a non-Douyin host; the fixture test must fail before restoring the correct code.
- [ ] Commit `feat: add native Douyin projection logic`.

### Task 4: MV3 Execution and Cleanup

**Files:**
- Create: `omnireach/chrome_extension/offscreen.js`
- Create: `omnireach/chrome_extension/service-worker.js`
- Modify: `omnireach/chrome_extension/manifest.json`
- Test: `tests/test_extension_manifest.py`
- Test: `tests/test_extension_js.py`

- [ ] Add failing static contract tests requiring `system.ping` and `douyin.search`
  allowlists, localhost bearer authorization, `chrome.windows.create` with `focused:false`,
  extraction via `chrome.scripting.executeScript`, and window removal in `finally`.
- [ ] Implement the offscreen authenticated long-poll loop and service-worker command
  dispatcher.
- [ ] Implement the self-contained injected DOM function that waits for rendered/login/
  empty/timeout states and returns serialized card payloads.
- [ ] Ensure every command returns the typed result envelope and every created window is
  removed in `finally`.
- [ ] Run static and JavaScript tests; commit `feat: add native Chrome execution layer`.

### Task 5: Transport Selection and Douyin Migration

**Files:**
- Create: `omnireach/browser_transport.py`
- Modify: `omnireach/adapters/douyin.py`
- Modify: `omnireach/sources.yml`
- Modify: `omnireach/commands/setup.py`
- Test: `tests/test_browser_transport.py`
- Modify: `tests/adapters/test_douyin.py`
- Modify: `tests/test_registry.py`
- Modify: `tests/test_cmd_setup.py`

- [ ] Write failing tests for `auto/native/opencli` selection, forced native never invoking
  OpenCLI, two-second native disconnect fallback, native runtime failures not falling back,
  cancellation cleanup, and the actual adapter label.
- [ ] Verify RED.
- [ ] Implement `BrowserCommandResult` and `run_browser_json`. Validate the transport env
  rather than silently accepting unknown values.
- [ ] Migrate only `DouyinAdapter` to the new boundary. `is_ready` accepts native config or
  OpenCLI; search records `native-chrome` or `opencli`.
- [ ] Change Douyin setup registry guidance to native bridge first with no automatic npm
  install; retain OpenCLI fallback documentation.
- [ ] Run focused adapter/router/setup tests and commit `feat: prefer native Chrome for Douyin`.

### Task 6: Real Chrome E2E, Documentation, and Release

**Files:**
- Modify: `README.md`
- Modify: `README.zh.md`
- Modify: `skills/omnireach/SKILL.md`
- Modify: `skills/omnireach/references/cli.md`
- Modify: `omnireach/__init__.py`
- Modify: `pyproject.toml`
- Modify: `.claude-plugin/plugin.json`
- Modify: `uv.lock`
- Create: `docs/releases/v0.14.0-alpha.md`

- [ ] Run `uv run omnireach bridge install --json` and load the reported stable directory as
  an unpacked extension in the user's normal Chrome profile.
- [ ] Run `uv run omnireach bridge status --json` and require connected true.
- [ ] Record visible Chrome windows/tabs, force native Douyin search, require live results
  with `adapter=native-chrome`, and verify visible state returns to baseline.
- [ ] Temporarily remove OpenCLI from the child process `PATH` while keeping Python available;
  repeat forced-native search to prove executable independence.
- [ ] Run auto mode and verify native is selected; use a temporary HOME without native config
  and verify auto fallback reaches OpenCLI.
- [ ] Update docs to state Douyin is native-first while other login-backed sources still use
  OpenCLI.
- [ ] Bump runtime/project/plugin to `0.14.0-alpha`, run `uv lock`, and add release notes.
- [ ] Run full pytest, Node tests, Ruff, diff check, build, Twine check, and fresh wheel E2E.
- [ ] Push PR, squash merge, tag merged main, create GitHub prerelease, publish exact artifacts
  to PyPI, fresh-install from public Simple API, upgrade the local global CLI, reinstall the
  stable extension assets without rotating the token, and run final forced-native E2E.
