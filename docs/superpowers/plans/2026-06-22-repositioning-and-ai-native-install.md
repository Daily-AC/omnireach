# Repositioning + AI-Native Install — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reframe omnireach's outward face from "patch proxy WebSearch" to "give your agent the senses of a logged-in human across the whole internet," and make install AI-native — one idempotent non-interactive command an agent runs on the human's behalf.

**Architecture:** Three independent deliverables. (1) `install.sh` at repo root: self-contained, idempotent, non-interactive; installs the CLI via uv and drops the canonical SKILL.md into `~/.claude/skills/omnireach/`. (2) Prose rewrite of SKILL.md description, README (+ `README.zh.md`), `plugin.json`, and the GitHub repo description — Senses/Eyes framing, three pillars first, technical gate explainer below the fold. (3) Demo GIF via the `hyperframes` plugin, embedded in the README.

**Tech Stack:** POSIX `sh`, `uv`, Claude Code skills-directory auto-discovery (`~/.claude/skills/<name>/SKILL.md`, confirmed via claude-code-guide), `hyperframes` plugin for the GIF, `shellcheck` for lint.

**Spec:** `docs/superpowers/specs/2026-06-22-repositioning-and-ai-native-install-design.md`

**Key facts (verified against the repo):**
- CLI is NOT on PyPI; install is `uv tool install git+https://github.com/Daily-AC/omnireach.git`. Entry point: `omnireach = "omnireach.cli:_entrypoint"` (pyproject `[project.scripts]`).
- Canonical skill lives at `.claude-plugin/skills/omnireach/SKILL.md` (single file, self-contained — safe to copy/fetch standalone).
- Claude Code auto-discovers `~/.claude/skills/<name>/SKILL.md` on next session; no slash command needed (claude-code-guide, v2.1+).
- `omnireach setup <source>` is interactive — the installer must NOT route through it. `omnireach init` is non-interactive and safe.

---

## Task 1: AI-native installer (`install.sh`)

**Files:**
- Create: `install.sh` (repo root)
- Create: `scripts/verify-install.sh` (lint + idempotency + behavior checks)

- [ ] **Step 1: Write the verification script (the "test") first**

Create `scripts/verify-install.sh`:

```sh
#!/bin/sh
# Verifies install.sh is agent-runnable: non-interactive, idempotent, and
# produces a working CLI + a discoverable skill file.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL="$ROOT/install.sh"
fail() { echo "FAIL: $1" >&2; exit 1; }

# 1. Lint (if shellcheck present)
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck "$INSTALL" || fail "shellcheck found issues"
  echo "ok: shellcheck clean"
fi

# 2. Non-interactive: no stdin reads / prompts in the script
if grep -Eq '(^|[^a-zA-Z_])read[[:space:]]' "$INSTALL"; then
  fail "install.sh contains an interactive 'read' — must be non-interactive"
fi
echo "ok: no interactive read"

# 3. Idempotent marker: uses --force on the CLI install and mkdir -p
grep -q 'uv tool install --force' "$INSTALL" || fail "CLI install must use --force (idempotent)"
grep -q 'mkdir -p' "$INSTALL" || fail "skill dir creation must use mkdir -p (idempotent)"
echo "ok: idempotency markers present"

echo "PASS: verify-install static checks"
```

- [ ] **Step 2: Run it to verify it fails (no install.sh yet)**

Run: `chmod +x scripts/verify-install.sh && scripts/verify-install.sh`
Expected: FAIL (or shellcheck error) because `install.sh` does not exist yet.

- [ ] **Step 3: Write `install.sh`**

Create `install.sh` at repo root:

```sh
#!/bin/sh
# omnireach AI-native installer — idempotent, non-interactive, self-contained.
# Human runs nothing; an agent runs:  curl -fsSL <raw-url>/install.sh | sh
set -eu

REF="${OMNIREACH_REF:-main}"
REPO="https://github.com/Daily-AC/omnireach.git"
RAW="https://raw.githubusercontent.com/Daily-AC/omnireach/${REF}"
SKILL_DIR="${HOME}/.claude/skills/omnireach"

say() { printf '%s\n' "$*"; }

# 1. Ensure uv is present (install it if missing — self-contained).
if ! command -v uv >/dev/null 2>&1; then
  say "→ installing uv (not found)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv lands in ~/.local/bin or ~/.cargo/bin — make this shell session see it.
  for d in "${HOME}/.local/bin" "${HOME}/.cargo/bin"; do
    [ -d "$d" ] && PATH="$d:$PATH"
  done
  export PATH
fi

# 2. Install / update the CLI (force = idempotent: re-running pulls latest).
say "→ installing omnireach CLI (ref: ${REF})…"
uv tool install --force "git+${REPO}@${REF}"

# 3. Non-interactive init (writes default ~/.omnireach/preferences.toml).
omnireach init >/dev/null 2>&1 || true

# 4. Register the skill for Claude Code (auto-discovered next session).
say "→ registering Claude Code skill at ${SKILL_DIR}…"
mkdir -p "${SKILL_DIR}"
if ! curl -fsSL "${RAW}/.claude-plugin/skills/omnireach/SKILL.md" -o "${SKILL_DIR}/SKILL.md"; then
  say "  (warning: could not fetch SKILL.md from ${REF}; CLI still installed)"
fi

say ""
say "✅ omnireach ready."
say "   • CLI:   omnireach search \"hello world\""
say "   • Skill: discovered by Claude Code on next session (just ask it to search)"
```

- [ ] **Step 4: Make executable and run the verifier**

Run: `chmod +x install.sh && scripts/verify-install.sh`
Expected: `PASS: verify-install static checks` (all `ok:` lines printed).

- [ ] **Step 5: Real E2E (project rule — mock does not count)**

Run the installer against this branch and confirm both effects. Use `OMNIREACH_REF` so it fetches the SKILL.md from this feature branch (the file isn't on `main` yet):

```sh
OMNIREACH_REF=feat/repositioning-ai-native-install sh install.sh
omnireach --version                        # CLI works
omnireach search --json "test" | head -c 200   # real search returns JSON
test -f "$HOME/.claude/skills/omnireach/SKILL.md" && echo "skill file landed"
# idempotency: run twice, second run must also succeed
OMNIREACH_REF=feat/repositioning-ai-native-install sh install.sh && echo "idempotent ok"
```

Expected: version prints, search returns a JSON envelope, "skill file landed", "idempotent ok".
Note: the `uv`-absent branch is exercised only if uv is missing; do not uninstall uv to test it. Static lint + the guarded code path cover it. A Docker clean-room run is the ideal future check (no CI yet).

- [ ] **Step 6: Commit**

```sh
git add install.sh scripts/verify-install.sh
git commit -m "feat: AI-native install.sh (idempotent, non-interactive) + verifier"
```

---

## Task 2: Rewrite SKILL.md (Senses/Eyes framing + correct install + step-0 self-heal)

**Files:**
- Modify: `.claude-plugin/skills/omnireach/SKILL.md` (frontmatter `description` + "第一次用" section)

- [ ] **Step 1: Rewrite the frontmatter `description`**

The description is what an agent reads to decide when to invoke. Lead with the capability (read 15+ platforms incl. login-walled verticals), demote the WebSearch-gate detail to the tail. Replace lines 1–4 (the frontmatter block) with:

```markdown
---
name: omnireach
description: Give your agent the senses of a logged-in human across the whole internet — search AND read 15+ platforms (Twitter / Reddit / 小红书 / 微信公众号 / 抖音 / B站 / TikTok / YouTube / HackerNews / GitHub / RSS) including the login-walled vertical sources that no web search reaches, via the user's own browser session. Two commands: `omnireach search <query>` (metadata + URL) and `omnireach fetch <url>` (full markdown). Use when the user wants to search or read any of these platforms, shares a URL to read, asks to research a topic, OR when Claude Code's built-in WebSearch is unavailable (proxy / relay-station / Bedrock / Vertex-Claude3.x environments where the web_search_20250305 server tool isn't implemented).
---
```

- [ ] **Step 2: Fix the broken install command + add step-0 self-heal**

In the "### 第一次用 (用户没装过)" section (currently `pipx install omnireach && omnireach init`, which is wrong — not on PyPI), replace that code block and add a self-heal note. New content for that section:

````markdown
### 第一次用 / step 0 (自愈)

如果 `omnireach` 不在 PATH (skill 在但 CLI 没装), 先跑这一条幂等命令装好 CLI + skill, 然后正常用:

```bash
curl -fsSL https://raw.githubusercontent.com/Daily-AC/omnireach/main/install.sh | sh
```

零配置即可用: hackernews / rss / wechat (Sogou 免费) / bilibili (B站官方 API)。其他源 (twitter / reddit / xhs / tiktok / douyin / boosters) 跑 `omnireach setup <source>` 解锁 (注意: `setup` 是交互式, 给人用; agent 别直接调)。
````

- [ ] **Step 3: Verify the rewrite**

Run:
```sh
grep -q "senses of a logged-in human" .claude-plugin/skills/omnireach/SKILL.md && echo "new framing ok"
grep -q "raw.githubusercontent.com/Daily-AC/omnireach/main/install.sh" .claude-plugin/skills/omnireach/SKILL.md && echo "install cmd ok"
! grep -q "pipx install omnireach" .claude-plugin/skills/omnireach/SKILL.md && echo "old broken cmd gone"
```
Expected: all three echo lines print.

- [ ] **Step 4: Commit**

```sh
git add .claude-plugin/skills/omnireach/SKILL.md
git commit -m "docs(skill): Senses/Eyes framing + fix install cmd + step-0 self-heal"
```

---

## Task 3: Rewrite README.md + README.zh.md + plugin.json + GitHub description

**Files:**
- Modify: `README.md` (full rewrite, English-first)
- Create: `README.zh.md` (Chinese mirror)
- Modify: `.claude-plugin/plugin.json:4` (`description`)
- External: GitHub repo description (via `gh`)

- [ ] **Step 1: Rewrite `README.md` (English-first)**

Replace the entire file. First screen = tagline + demo GIF + install + three pillars. Technical gate explainer + naming go into `<details>` blocks below the fold. Skeleton (fill source/command tables from the current README's accurate content — they stay correct):

```markdown
# omnireach

<sub>English · [中文](./README.zh.md)</sub>

**Give your AI agent the senses of a logged-in human — across the entire internet.**

Search and read **15+ platforms** — including the vertical, login-walled sources
(**Twitter · Reddit · 小红书 · 微信 · 抖音 · B站 · TikTok**) that every agent web search
is blind to — through your own browser session. One uniform interface. Installed as a
skill, so your agent just knows how to use it.

![demo](./docs/assets/demo.gif)

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)

## Install — just tell your agent

> **"Install omnireach"**

Your agent runs one command. You copy nothing.

<sub>Prefer to do it yourself, or no agent handy?</sub>

```bash
curl -fsSL https://raw.githubusercontent.com/Daily-AC/omnireach/main/install.sh | sh
```

This installs the `omnireach` CLI and registers the Claude Code skill (auto-discovered
next session). Zero-config sources work immediately; HackerNews/RSS/微信/B站 need nothing.

## What you get

**1. Reach the unreachable.** Twitter timelines, Reddit threads, 小红书 notes, 微信公众号
articles, 抖音 / B站 / TikTok videos — login-walled vertical platforms that *no* agent web
search reaches. omnireach reads them through your own logged-in browser session.

**2. One uniform contract.** `omnireach search` returns normalized metadata + URL; `omnireach
fetch` returns clean markdown. Same shape across every source — your agent learns one
interface, not 15 APIs.

**3. Works even when WebSearch doesn't.** On proxy / relay-station / Bedrock / Vertex-Claude3.x
setups where the built-in WebSearch server tool isn't available, omnireach gives search back.

## Example

```bash
omnireach search --on xiaohongshu --json "Claude Code 使用技巧"
omnireach fetch  --json "https://mp.weixin.qq.com/s/<token>"   # login-walled, via your session
```

## Commands

(— keep the command table from the current README; it is accurate —)

## Sources

(— keep the sources table from the current README; it is accurate —)

## Agent calling convention

Always pass `--json` (or `export OMNIREACH_FORCE_JSON=1`). Details in [SKILL.md](./.claude-plugin/skills/omnireach/SKILL.md).

<details>
<summary><b>Who specifically needs this? (the WebSearch two-layer gate)</b></summary>

(— move the entire "为什么需要 omnireach" two-layer-gate explainer here, translated to English, unchanged in substance —)
</details>

<details>
<summary><b>Naming &amp; architecture (search / fetch / parse)</b></summary>

(— move the "关于命名" sibling-binary / three-layer table here —)
</details>

## Upgrade · Platform support · Boosters · Preferences · Full text

(— keep these sections from the current README; relocate below the fold —)

## License

MIT — see [LICENSE](LICENSE).
```

Preserve every accurate table (commands, sources, fetch backends, platform support, full-text
mapping) from the current README verbatim — only the *order and framing* change, not the facts.

- [ ] **Step 2: Create `README.zh.md` (Chinese mirror)**

Mirror the new structure in Chinese. Tagline: **「给你的 AI agent 装上一个登录态人类的全套感官 —— 触达整个互联网。」** Reuse the accurate Chinese tables already in the current README. Top line: `<sub>[English](./README.md) · 中文</sub>`.

- [ ] **Step 3: Rewrite `plugin.json` description**

Edit `.claude-plugin/plugin.json` line 4. Replace the `description` value with:

```json
  "description": "Give your agent the senses of a logged-in human across the whole internet — search & read 15+ platforms (Twitter/Reddit/小红书/微信/抖音/B站/TikTok/YouTube/HN/GitHub/RSS) the web can't reach.",
```

- [ ] **Step 4: Update the GitHub repo description**

Run:
```sh
gh repo edit Daily-AC/omnireach --description "Give your AI agent the senses of a logged-in human across the whole internet — search & read 15+ platforms (Twitter/Reddit/小红书/微信/抖音/B站/TikTok/YouTube/GitHub) no web search reaches. Install by telling your agent."
```

- [ ] **Step 5: Verify**

Run:
```sh
head -5 README.md | grep -q "senses of a logged-in human" && echo "readme tagline ok"
test -f README.zh.md && echo "zh mirror exists"
grep -q "senses of a logged-in human" .claude-plugin/plugin.json && echo "plugin desc ok"
# first screen must NOT lead with the gate explainer
! head -20 README.md | grep -q "isEnabled\|web_search_20250305" && echo "gate explainer below fold"
gh repo view Daily-AC/omnireach --json description -q .description | grep -q "senses of a logged-in" && echo "gh desc ok"
```
Expected: all five echo lines print.

- [ ] **Step 6: Commit**

```sh
git add README.md README.zh.md .claude-plugin/plugin.json
git commit -m "docs: rewrite README/description — Senses/Eyes framing, three pillars, AI-native install"
```

---

## Task 4: Demo GIF via hyperframes

**Files:**
- Create: `docs/assets/demo.gif`
- (README already references `./docs/assets/demo.gif` from Task 3)

- [ ] **Step 1: Install the hyperframes plugin**

```sh
claude plugin marketplace add heygen-com/hyperframes
claude plugin install hyperframes@hyperframes --scope user
```
If the `claude plugin` CLI is unavailable (older Claude Code), fall back to the interactive
`/plugin marketplace add heygen-com/hyperframes` + `/plugin install hyperframes`. Confirm the
plugin loaded (`claude plugin list` shows hyperframes, or its tools appear). Read its
SKILL/README to learn the exact GIF-generation invocation before recording.

- [ ] **Step 2: Record the real flow**

Storyboard (use the *real* commands, not a mock):
1. Human prompt: *"装一下 omnireach，然后帮我搜小红书上关于 Claude Code 的讨论"*
2. Agent runs: `curl -fsSL .../install.sh | sh` (the one-liner provisions everything)
3. Agent runs: `omnireach search --on xiaohongshu --json "Claude Code"`
4. Results render.

Drive hyperframes per its documented API to produce a GIF of this sequence. Keep it short
(≤ ~15s) and legible at README width (~900px). Save to `docs/assets/demo.gif`.

- [ ] **Step 3: Verify the GIF exists and is referenced**

Run:
```sh
test -f docs/assets/demo.gif && echo "gif exists"
grep -q "docs/assets/demo.gif" README.md && echo "gif referenced in README"
# sanity: non-trivial file size (not an empty/placeholder)
[ "$(wc -c < docs/assets/demo.gif)" -gt 10000 ] && echo "gif non-trivial size"
```
Expected: all three echo lines print. Also open the GIF and confirm it visually plays the flow.

- [ ] **Step 4: Commit**

```sh
git add docs/assets/demo.gif
git commit -m "docs: add demo GIF (ask-agent-to-install → search 小红书 flow)"
```

---

## Task 5: Finish the branch

**Files:**
- Modify: `README.md` / `CLAUDE.md` changelog line (optional version note)
- Modify: `omnireach/__init__.py` `__version__` (if bumping)

- [ ] **Step 1: Full test suite still green**

Run: `uv run pytest -q`
Expected: all existing tests pass (this work touches docs + a shell script + a skill file; no
Python behavior changed, so the 278 tests should be unaffected). If any fail, fix before
proceeding.

- [ ] **Step 2: Decide + apply version bump (ask the user)**

This adds real behavior (install.sh, SKILL step-0) atop the doc rewrite. Propose `v0.11.0-alpha`.
If approved: bump `omnireach/__init__.py` `__version__`, add a changelog entry to README/CLAUDE.md
following the existing `vX.Y.Z-alpha` style, commit.

- [ ] **Step 3: Hand off to finishing-a-development-branch**

Use the `superpowers:finishing-a-development-branch` skill to push, open the PR, squash-merge,
tag, and `gh release create` per the project's release flow (CLAUDE.md "Release 流程"). Remember:
after creating the release, `gh release edit vLATEST --latest` if needed so `check-update` resolves.

---

## Self-Review

**Spec coverage:**
- §3 positioning rewrite → Task 2 (SKILL), Task 3 (README/zh/plugin/GitHub desc). ✓
- §4 AI-native install (idempotent/non-interactive/self-contained, skills-dir registration, raw.githubusercontent hosting) → Task 1. ✓
- §4.6 SKILL step-0 self-heal → Task 2 Step 2. ✓
- §5 demo GIF via hyperframes → Task 4. ✓
- §6 deliverables (description, README, README.zh, install.sh, SKILL, demo.gif) → Tasks 1–4. ✓
- §7 success criteria → verification steps in each task + Task 1 Step 5 real E2E. ✓
- §8 open question (skill registration) → resolved: skills-dir drop (claude-code-guide confirmed), §Key facts. Bilingual layout → separate README.zh.md (Task 3 Step 2). Windows installer → deferred (POSIX sh only; note in spec stands). ✓

**Placeholder scan:** Source/command/platform tables in Task 3 are marked "keep from current README" with explicit instruction to preserve verbatim — not a placeholder, a preservation directive (the content already exists and is accurate). All code/shell steps show full content.

**Type/string consistency:** install URL `raw.githubusercontent.com/Daily-AC/omnireach/main/install.sh` identical in Task 1 (script self-ref via RAW+REF), Task 2 (SKILL step-0), Task 3 (README). Skill dir `~/.claude/skills/omnireach/` consistent. Tagline string "senses of a logged-in human" consistent across SKILL desc, README, plugin.json, and all verify greps.
