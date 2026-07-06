# omnireach

<sub>English · [中文](./README.zh.md)</sub>

**Your agent reads Twitter. It still can't read WeChat. omnireach fixes that.**

omnireach searches and reads the login-walled Chinese internet — 微信公众号 · 小红书 · 抖音 · B站 · TikTok — plus Twitter, Reddit, HN, YouTube and more, through one uniform interface: `omnireach search` returns one normalized JSON schema across every source, `omnireach fetch` returns clean markdown for any URL. WeChat search works with **zero config** — no key, no login:

```bash
omnireach search --on wechat "Claude Code 技巧"   # works 60 seconds after install
```

Installed as a Claude Code skill, so your agent just knows how to use it next session. No LLM inside, no per-call scraping fees — the heavy sources reuse your own browser session.

![demo — zero-config WeChat search, uniform JSON across sources](./docs/assets/demo-wechat.gif)

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)

---

## Install — just tell your agent

> **"Install omnireach"**

Your agent runs one command. You copy nothing.

<sub>Manual fallback — paste into your terminal if you prefer:</sub>

```bash
curl -fsSL https://raw.githubusercontent.com/Daily-AC/omnireach/main/install.sh | sh
```

<sub>Also on [PyPI](https://pypi.org/project/omnireach/): `uv tool install omnireach` or `pip install omnireach` (CLI only — the one-liner above additionally registers the Claude Code skill). Try without installing: `uvx omnireach search "vibe coding"`.</sub>

This installs the CLI **and** registers the Claude Code skill (auto-discovered next session). Zero-config sources — HackerNews, RSS, 微信 (Sogou path), B站 — work immediately. Other sources open up after a one-time setup step each.

---

## What you get

**1. Reach the unreachable.**
Twitter, Reddit, 小红书, 微信公众号, 抖音, B站, TikTok — login-walled vertical platforms that no agent web search reaches. omnireach reads them through your own logged-in browser session (via OpenCLI Chrome bridge), so the results your agent sees are the same results a human would see when signed in.

**2. One uniform contract.**
`omnireach search` → normalized metadata + URL, same shape across every source. `omnireach fetch` → clean markdown for any URL, with host-aware routing (`mp.weixin.qq.com` goes through your logged-in Chrome session to bypass CAPTCHA walls; all other hosts go through Crawl4AI → Jina Reader fallback). Your agent learns one interface, not 15 APIs.

**3. Works even when WebSearch doesn't.**
On proxy / relay-station / Bedrock / Vertex-Claude-3.x setups where the built-in WebSearch server tool isn't available, omnireach gives search back — it runs entirely on the client side, bypassing both gate layers.

---

## How is this different from Agent-Reach?

[Agent-Reach](https://github.com/Panniantong/Agent-Reach) (51k★) created this category and is excellent at what it does. omnireach makes different trade-offs — these are date-stamped facts, not marketing:

| | omnireach | Agent-Reach (v1.5.0, as of 2026-07) |
|---|---|---|
| 微信公众号 WeChat | ✅ zero-config search (Sogou path) + full-text fetch via your logged-in Chrome | ❌ removed 2026-06 ([PR #347](https://github.com/Panniantong/Agent-Reach/pull/347)) after anti-bot breakage |
| 抖音 Douyin | ✅ search via your logged-in Chrome | ❌ removed 2026-06 (upstream tool archived) |
| TikTok | ✅ search | ❌ not supported |
| Output contract | one pydantic JSON schema across all 16 sources; auto-JSON when piped | no wrapper layer by design — each upstream tool's own format (YAML / plain text / subtitle files / raw JSON) |
| `search` / `fetch` commands | built-in: `omnireach search`, `omnireach fetch <url>` with host-aware routing | no search/read commands — routes your agent to call upstream tools directly |
| Facebook · Instagram · LinkedIn · 雪球 · podcast transcription | ❌ | ✅ |
| Community | early — you found us before the crowd | 51k★, 30 contributors |

Pick Agent-Reach if you need Facebook/LinkedIn/transcription. Pick omnireach if you need the Chinese internet — WeChat above all — a machine-stable JSON contract, or a single fetch entrypoint. Both MIT; they compose fine in one agent.

---

## Example

```bash
# Search a login-walled vertical platform
omnireach search --on xiaohongshu --json "Claude Code 使用技巧"

# Fetch a WeChat article — login-walled, via your session
omnireach fetch --json "https://mp.weixin.qq.com/s/<token>"

# Full pipeline: search → fetch all results
omnireach search --on wechat --json "claude 4.7" \
  | jq -r '.results[].url' \
  | xargs -I{} omnireach fetch --json {}
```

---

## Commands

| Command | What it does |
|---|---|
| `omnireach search "<query>"` | Search (SERP: metadata + URL) |
| `omnireach search --on twitter,reddit "..."` | Target specific sources |
| `omnireach search --mode quick "..."` | Quick mode — HN only |
| `omnireach search --mode deep "..."` | Deep mode — all ready sources |
| `omnireach search --json "..."` | Explicit JSON output |
| **`omnireach fetch <url>`** (v0.10, v0.10.1) | **URL → full markdown** — `mp.weixin.qq.com` uses OpenCLI logged-in Chrome (v0.10.1+), other hosts use crwl → jina fallback |
| `omnireach fetch <url> --backend jina` | Force Jina Reader SaaS (zero local deps) |
| `omnireach fetch <url> --backend opencli` | Force OpenCLI wechat logged-in path (v0.10.1+) |
| `omnireach init` | Write default `~/.omnireach/preferences.toml` |
| `omnireach sources` | List all sources + tier status |
| `omnireach setup <source>` | Guided setup for a 🟡 / 🔴 source |
| `omnireach doctor` | Health check (sources / fetch backends / wechat backends) |

---

## Sources

| Source | Tier | Dependency | Notes |
|---|---|---|---|
| hackernews | ✅ ready | none | Direct Algolia, zero-config |
| youtube | ✅ ready | `yt-dlp` (pip install) | `omnireach setup youtube` |
| github | ✅ ready | `gh` CLI + `gh auth login` | `omnireach setup github` |
| rss | ✅ ready | built-in feedparser | query must be a URL |
| reddit | 🟡 one_step | `rdt-cli` + `rdt login` | `omnireach setup reddit` |
| twitter | 🔴 heavy | OpenCLI + Chrome extension | v0.3 path |
| xiaohongshu | 🔴 heavy | OpenCLI + Chrome extension | v0.3 path |
| tiktok | 🔴 heavy | OpenCLI + Chrome extension | TikTok international (v0.7) |
| douyin | 🔴 heavy | OpenCLI fork + Chrome extension | 抖音 (v0.7.2, Daily-AC/OpenCLI fork) |
| 💎 tavily | booster | env `TAVILY_API_KEY` | paid (v0.4) |
| 💎 brave | booster | env `BRAVE_API_KEY` | paid (v0.4) |
| 💎 perplexity | booster | env `PERPLEXITY_API_KEY` | paid (v0.4) |
| 💎 exa | booster | env `EXA_API_KEY` | paid web search (v0.5) |
| wechat | ✅ ready | none (optional `EXA_API_KEY` for enhancement) | WeChat Official Accounts — search via Sogou free path; `EXA_API_KEY` optionally enables semantic enhancement; v0.10.1+ `omnireach fetch <wechat-url>` auto-routes through OpenCLI logged-in Chrome |
| bilibili | ✅ ready | none (optional `EXA_API_KEY` for enhancement) | B站 — v0.9+ defaults to B站 official search API; `EXA_API_KEY` optionally enables semantic enhancement |

> **抖音 / douyin** (v0.7.2): Uses `omnireach setup douyin`, installs [Daily-AC/OpenCLI fork](https://github.com/Daily-AC/OpenCLI) (upstream PR [jackwener/OpenCLI#1759](https://github.com/jackwener/OpenCLI/pull/1759) pending review; will switch back once merged). Requires signing in to www.douyin.com in Chrome. `engagement.likes` has real data (DOM extraction); `plays/comments/shares` are not exposed in search cards, normalized to `null`.

> **WeChat fetch** (v0.10.1): `omnireach fetch <mp.weixin.qq.com URL>` uses the same Daily-AC/OpenCLI fork (`weixin download --stdout`, upstream PR [jackwener/OpenCLI#1770](https://github.com/jackwener/OpenCLI/pull/1770) pending). Requires having opened any mp.weixin.qq.com article in Chrome (no explicit login step; browser cookies suffice). See [How to get full text](#how-to-get-full-text-v08) below.

---

## Agent calling convention

When calling omnireach from an agent, **always request JSON explicitly** to prevent rich-table output from wrapping fields you need:

```bash
# Option 1: explicit flag per command
omnireach search --json "..."
omnireach fetch  --json "<url>"

# Option 2: env var (recommended for agent harnesses)
export OMNIREACH_FORCE_JSON=1
```

The `not isatty()` auto-JSON added in v0.9.2 covers most cases, but some agent terminals (e.g. Antigravity) allocate a real PTY to subprocesses making `isatty()=True`. Explicit `--json` or the env var always works.

Full skill contract: [`.claude-plugin/skills/omnireach/SKILL.md`](./.claude-plugin/skills/omnireach/SKILL.md)

---

<details>
<summary><b>Who specifically needs this? (The WebSearch two-layer gate)</b></summary>

Claude Code's WebSearch is a **server-side server tool** (`web_search_20250305`). Whether it actually works depends on **two independent gates**:

**Gate 1 — client-side (`WebSearchTool.isEnabled()` checks `getAPIProvider()`):**
- Default `firstParty` (no `CLAUDE_CODE_USE_*` env var set, including the case where only `ANTHROPIC_BASE_URL` is changed) → tool **registered**
- Explicit `CLAUDE_CODE_USE_BEDROCK=1` → tool **off**
- Explicit `CLAUDE_CODE_USE_VERTEX=1` + Claude 4+ → registered; older Claude → off
- Explicit `CLAUDE_CODE_USE_FOUNDRY=1` → registered

**Gate 2 — upstream server tool implementation:** After the client sends the tool schema, the upstream API must have **specifically implemented** the `web_search_20250305` server tool (receive tool call → run search → return results to client):
- Real Anthropic API (api.anthropic.com): ✓ native
- Vertex / Foundry: ✓ (each backend implements it)
- **Third-party providers that specifically support Claude Code** (e.g. DeepSeek's Anthropic-compat endpoint): ✓ they implemented the server tool handling, routing to their own search backend
- **OpenAI-compatible relay stations** (cliproxy / anyrouter etc. that simply translate Claude API → OpenAI Chat Completions): ✗ don't recognize server tool semantics
- **Self-hosted gateways / most proxies**: ✗ generally not implemented

Gate 2 looks at **"did the upstream specifically implement Claude Code server tool support"** — not at "is this real Anthropic." Providers who specifically support Claude Code implement it; pure API translators don't. (Data point: DeepSeek is not real Anthropic but WebSearch works because they explicitly implemented it.)

**Root causes differ by scenario:**
- DeepSeek and other Claude-Code-specific third parties: both gates pass, WebSearch ✓ — omnireach value here is supplementing vertical sources (Twitter/小红书/微信), not patching search
- OpenAI-compatible relay station users: client registers the tool, **upstream doesn't handle the server tool call** → failure
- Explicit Bedrock users / Vertex Claude 3.x users: client-side `isEnabled` is off before the request even leaves

**Even with WebSearch working**, it can't reach Twitter threads, Reddit comment sections, 小红书 posts, WeChat articles, 抖音, B站 technical videos — these login-walled vertical platforms are blind spots for every hosted web search. omnireach's three value layers:
1. Patch for users whose client-side gate is off
2. Patch for users whose upstream doesn't implement the server tool
3. Supplement for users whose WebSearch works fine but can't reach vertical platforms

</details>

<details>
<summary><b>Naming & architecture (search / fetch / parse)</b></summary>

**omnireach** = `omni` (all) + `reach` (reach). Full "reach the whole web" semantics require three capability layers, all living as **sibling binaries in this repo** (analogous to `cargo` / `rustc` / `rustfmt` in the Rust monorepo — **no sister repo**):

| Layer | Implementation | Responsibility | Status |
|---|---|---|---|
| **search** | `omnireach search` subcommand | Locate across the web — returns metadata + URL, does not fetch content | ✅ v0.7+ in use |
| **fetch** | `omnireach fetch` subcommand | Given a URL, fetch full-text markdown — host-aware: `mp.weixin.qq.com` via OpenCLI logged-in Chrome, others via [Crawl4AI](https://github.com/unclecode/crawl4ai) → [Jina Reader](https://r.jina.ai/) | ✅ v0.10+ (wechat path v0.10.1+) |
| **parse** | (not yet implemented, future addition to this repo) | Video/audio content parsing (subtitles/STT/frame-by-frame) | 🔜 not started |

v0.10+ has omnireach covering search + fetch (subcommand form). Video parsing still uses external tools (yt-dlp / whisper); parse binary will be added to this repo when there are real user requests (YAGNI — no sister repo).

This split mirrors Anthropic's own [WebSearch](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-search) + [WebFetch](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-fetch) split: each layer does one thing well, search isn't slowed by parsing tasks, and agent callers can compose freely.

> Note: renaming `omnireach` to `omnisearch` was considered, but v0.10 landing `omnireach fetch` resolved the question — `omnireach search` (reach = find) + `omnireach fetch` (reach = retrieve) are both natural sub-actions of "reach," so the umbrella name fits. **No rename** (decided 2026-05-27).

</details>

<details>
<summary><b>Upgrade</b></summary>

omnireach is in alpha with frequent releases. Check and upgrade:

```bash
omnireach check-update                                                            # compare against GitHub Releases
uv tool install --force git+https://github.com/Daily-AC/omnireach.git             # pull latest
```

> ⚠️ `uv tool upgrade omnireach` **will not** pull new commits (uv locks git-URL-installed tools to the commit at install time). `--force` reinstall fetches the latest.

</details>

<details>
<summary><b>Platform support</b></summary>

| Platform | Status | Notes |
|---|---|---|
| macOS | ✅ Primary dev platform | All sources tested (HN/RSS/youtube/github/reddit/twitter/xhs/tiktok/douyin + 4 boosters + wechat/bilibili); `omnireach fetch` all three backends (crwl/jina/opencli) verified |
| Linux | 🟡 best-effort | Should work; setup flow doesn't auto-detect `apt`/`pacman` |
| WSL2 | 🟡 best-effort | Same as Linux |
| Windows (native PowerShell) | 🟡 experimental (v0.6.3+) | macOS assumptions removed: secrets.env no longer calls POSIX chmod; preferences edit falls back to notepad; setup github prompts `winget install GitHub.cli`; OpenCLI sources (twitter/xhs) theoretically cross-platform but untested. **File an issue if you hit problems.** |

Run `omnireach doctor` to print a platform / Python version line at the top — useful to include when filing issues.

</details>

<details>
<summary><b>💎 Paid boosters (v0.4)</b></summary>

omnireach is free by default. Configuring a paid API key improves result quality:

```bash
omnireach setup tavily       # guided key entry + writes to ~/.omnireach/secrets.env
omnireach setup brave
omnireach setup perplexity
omnireach setup exa          # added v0.5 (replaces old `web` source)
```

Keys are detected automatically when set. Results carry `cost="paid"` metadata; TTY output shows a 💎 prefix for auditability.

To disable: edit `~/.omnireach/preferences.toml` and set `[boosters] auto_enable = false`.

</details>

<details>
<summary><b>⚙️ User preferences (v0.4)</b></summary>

`~/.omnireach/preferences.toml` can configure default sources, language, output format, and `source_trust` overrides.

```bash
omnireach preferences show     # view current config
omnireach preferences edit     # open in $EDITOR
omnireach preferences reset    # reset (backs up original to .bak)
omnireach preferences path     # print file location
```

</details>

<details>
<summary><b>How to get full text (v0.8)</b></summary>

omnireach is the search layer — the `content` field is uniformly capped at ≤ 500 characters + `…`. This validator runs in the contract layer (`SearchResult.content` pydantic `field_validator`) for **all sources**. This is intentional — full text belongs to the `omnireach fetch` layer (see [Naming & architecture](#naming--architecture-search--fetch--parse) above).

For sources whose upstream returns full text (wechat / exa / tavily) or long threads (twitter), the **complete raw payload is preserved in `result.raw`**, so agents that need full text can retrieve it:

```python
# Python (call CLI + parse JSON envelope)
import json
import subprocess

out = subprocess.run(
    ["omnireach", "search", "--json", "--on", "wechat", "claude 4.7"],
    check=True, capture_output=True, text=True,
)
env = json.loads(out.stdout)
snippet = env["results"][0]["content"]        # 500 chars + "…"
full    = env["results"][0]["raw"]["text"]    # Exa / wechat / twitter full text
# tavily uses raw["content"]
```

```bash
# CLI + jq
omnireach search --json --on tavily "claude 4.7" | \
  jq '.results[] | {title, snippet: .content, full: .raw.content}'
```

Field mapping (verified by real E2E in v0.8.1 + v0.9):

| Source | `result.adapter` | `result.content` | `result.raw[...]` for full text / raw payload |
|---|---|---|---|
| wechat (default Sogou) | `sogou` | snippet (Sogou SERP summary) | `raw["item_html"]` (full Sogou card HTML) — for actual full text you need mp.weixin.qq.com |
| wechat (EXA_API_KEY enabled) | `exa-api` | snippet | `raw["text"]` (Exa full text) |
| bilibili (default B站 API) | `bilibili-api` | video description (≤500) | `raw` entire video item dict, includes desc/cover/aid/bvid |
| bilibili (EXA_API_KEY enabled) | `exa-api` | snippet | `raw["text"]` |
| exa | `exa-api` | snippet | `raw["text"]` |
| tavily | `tavily-api` | snippet | `raw["content"]` |
| twitter | `opencli` | snippet (long threads trigger truncation) | `raw["text"]` |
| xiaohongshu | `opencli` | empty — OpenCLI search results don't include body | n/a (no full text at search layer) |

The specific key names in `raw[...]` match upstream API schema directly — if upstream changes schema, this table needs updating. When uncertain, inspect `result.raw.keys()` first.

Other sources (HN / GitHub / RSS / YouTube / etc.) generally have content under 500 chars, so the validator is usually a no-op — but it's not guaranteed. For full-text fallback, check `result.raw` for a matching key.

### For actual full text → `omnireach fetch <url>` (v0.10+)

`omnireach fetch <url>` is the official search → full-text pipeline, with **host-aware** backend routing:

```bash
# Any webpage → crwl (local Crawl4AI) preferred, jina (r.jina.ai SaaS) fallback
omnireach fetch https://example.com/article --json

# WeChat Official Account article → automatically uses OpenCLI logged-in Chrome (v0.10.1+), bypasses CAPTCHA
omnireach fetch https://mp.weixin.qq.com/s/<token> --json

# search → fetch pipeline
omnireach search --on wechat "claude 4.7" --json \
  | jq -r '.results[].url' \
  | xargs -I{} omnireach fetch --json {}
```

Backend matrix:

| URL host | `--backend auto` routes to | Notes |
|---|---|---|
| `mp.weixin.qq.com` | **opencli** (logged-in cookie strategy) | Install [Daily-AC/OpenCLI fork](https://github.com/Daily-AC/OpenCLI) with `weixin download --stdout` flag (v0.10.1 commit fe28823+); direct `crwl` / `jina` are blocked by WeChat's "environment anomaly" CAPTCHA |
| Other hosts | **crwl → jina** | Crawl4AI preferred; falls back to Jina Reader SaaS if not installed or fails |

Explicit `--backend` overrides auto:

| Flag | Behavior |
|---|---|
| `--backend crwl` | Force Crawl4AI local (66K ⭐ Apache-2.0, built-in Cloudflare/Akamai/DataDome bypass) |
| `--backend jina` | Force [Jina Reader](https://r.jina.ai/) SaaS — zero local deps, large free tier |
| `--backend opencli` | Force OpenCLI wechat logged-in path (only meaningful for mp.weixin.qq.com) |

v0.10.1 adds **CAPTCHA heuristic fallback** for all backends: when keywords like `环境异常 / 完成验证后即可继续访问 / Cloudflare / Just a moment` are detected, the envelope `errors[]` gains a `captcha_suspected: ...` entry; the markdown field is preserved (graceful degrade — agent reads `errors` to decide whether to trust the content). `omnireach doctor`'s `wechat_backends` section surfaces whether OpenCLI + `--stdout` are ready.

</details>

<details>
<summary><b>Design</b></summary>

See `docs/superpowers/specs/2026-05-25-omnireach-design.md`.

</details>

<details>
<summary><b>License</b></summary>

MIT — see [LICENSE](LICENSE).

</details>
