# omnireach — Repositioning + AI-Native Install (Design Spec)

**Date:** 2026-06-22
**Status:** Approved (brainstorming), pending implementation
**Author:** 甲方 (张以琳) + Claude

## 1. Problem

The repo is engineering-sound but adoption-starved (4★ at 4 weeks). Two outward-facing
defects, both about how a stranger or an agent first meets the project:

1. **Positioning is narrowed to the iceberg's tip.** Today's README + GitHub description
   lead with "补齐中转站 Agent 用户的 WebSearch" and open with naming philosophy + a
   two-layer-gate technical explainer. A stranger's first 3 seconds read "a tool that
   patches a proxy bug" — not "eyes on the whole internet for my agent." The deepest,
   most differentiated value (search + read 15+ login-walled vertical platforms that no
   web search reaches) is buried at line ~51.

2. **Install is not AI-native.** Current path needs `uv tool install …` plus a separate
   `/plugin marketplace add` + `/plugin install` dance. The human copies multiple
   commands; nothing collapses the work into the agent.

## 2. Goals

- Rewrite the GitHub **description** and **README** so a stranger understands what
  omnireach is, why they need it, and wants it — within the first screen.
- Make install **AI-native**: the human's entire job is one sentence in natural language;
  the agent runs a single idempotent command that provisions everything. A manual
  one-liner exists as the secondary "I'd rather do it myself" path.
- Produce a **demo GIF** of the real flow (ask-the-agent-to-install → search a vertical
  source) using the `hyperframes` plugin.

Non-goals: no new search/fetch sources, no architecture changes, no parse layer. This is
a packaging/positioning pass, not a feature pass. The three-layer architecture boundary
(search/fetch/parse) is unchanged.

## 3. Positioning (the rewrite's spine)

### 3.1 Core insight — Web ≠ Internet

WebSearch (even the real Anthropic one) only sees the **indexed open web**. The internet
humans actually live in is mostly **behind logins and inside vertical apps**: Twitter
timelines, Reddit threads, 小红书 notes, 微信公众号 articles, 抖音/B站/TikTok videos,
YouTube transcripts, GitHub. **No agent's web search reaches any of it.**

### 3.2 The one true sentence (approved tagline — Senses/Eyes metaphor)

> **Give your AI agent the senses of a logged-in human — across the entire internet.**
>
> Search and read 15+ platforms, including the vertical, login-walled sources (Twitter,
> Reddit, 小红书, 微信, 抖音, B站) that every agent web search is blind to.

Brand note: this deliberately rhymes with the already-installed `agent-reach` skill's
"eyes to see the entire internet" line — consistent family voice.

### 3.3 Three pillars (replace the two-layer-gate opener)

1. **Reach the unreachable** — login-walled vertical platforms (Twitter / Reddit / 小红书
   / 微信 / 抖音 / B站 / TikTok), via *your own browser's logged-in session*. No competing
   agent tool gives this. **This is the iceberg's body — first screen.**
2. **One uniform contract** — 15 sources, `search` returns normalized metadata + URL,
   `fetch` returns clean markdown, same shape everywhere. The agent learns one interface,
   not 15 APIs.
3. **Works even when WebSearch doesn't** — proxy / Bedrock / Vertex-3.x users get search
   back. **Demoted from headline to footnote.**

### 3.4 What moves where

- The two-layer-gate explainer (client `isEnabled()` gate + upstream server-tool gate) is
  **kept** but relocated to an end-of-README collapsible "Who specifically needs this?"
  section. It is precise and valuable for the proxy-user segment, but it does not belong
  on the first screen.
- Naming philosophy (sibling-binary / cargo analogy) moves below the fold too.

## 4. AI-Native Install

### 4.1 Principle

There is exactly **one idempotent, non-interactive, self-contained command** that fully
provisions omnireach. The human types a sentence; the agent runs that command.

```
Human:  "Install omnireach"                          ← only human input, natural language
  ↓
Agent:  curl -fsSL <install-url> | sh                 ← agent runs it; human copies nothing
  ↓
Script: ① ensure uv present  → ② uv tool install omnireach (CLI)
        ③ register the skill into ~/.claude/skills/   → ④ print "✅ ready"
  ↓
Next turn: skill is in context; agent uses omnireach natively. Human did nothing else.
```

### 4.2 Hard requirements on the installer (all in service of "an agent can run it")

- **Non-interactive** — zero prompts/confirms. A prompt deadlocks an agent on stdin.
  (Current `omnireach setup <source>` is interactive — leave it as-is for humans; the
  installer must NOT route through it.)
- **Idempotent** — safe to re-run; re-running detects existing install and no-ops/updates.
- **Self-contained** — installs `uv` if absent; assumes nothing about the environment.
- **Does two jobs in one command** — installs the CLI *and* registers the skill, so there
  is no "step 2."
- **Quiet, pipe-safe output** — echoes a short status, ends with a clear ready line; nothing
  that becomes a nightmare in an agent's stdout pipe (consistent with the project's
  Agent-first CLI UX preference).

### 4.3 What the installer does NOT do

- Does **not** set up 🔴 heavy sources (Twitter/小红书/抖音 need a browser login — inherently
  interactive). It provisions the zero-config ready state (HN works immediately) and leaves
  per-source `setup` to the human/agent on demand.
- Does **not** require a GitHub remote login or any paid key.

### 4.4 Hosting the one-liner

Default to `curl -fsSL https://raw.githubusercontent.com/Daily-AC/omnireach/main/install.sh | sh`
— zero extra infra (no GitHub Pages needed, works the moment the file lands on `main`). A
prettier `daily-ac.github.io/omnireach/install.sh` vanity URL is a later nicety, not a
blocker.

### 4.5 Skill registration — OPEN QUESTION (verify during impl)

Two candidate mechanisms; pick during implementation after verifying current Claude Code
behavior (use the `claude-code-guide` agent):

- **(a) User-level skill drop** — installer copies `SKILL.md` (+ any assets) into
  `~/.claude/skills/omnireach/`. Simplest non-interactive path; auto-discovered next
  session.
- **(b) Plugin marketplace registration** — installer writes the marketplace config that
  `/plugin marketplace add` + `/plugin install` would produce. Matches the existing
  `.claude-plugin/` manifest but the slash-command flow is interactive-by-default.

Lean **(a)** for the non-interactive installer; keep the plugin/marketplace path documented
for humans who prefer slash commands. Confirm exact dirs/format before writing the script.

### 4.6 SKILL.md step-0 self-heal (safety net)

Add a "step 0" to SKILL.md: before first use, the agent checks `omnireach` is on PATH; if
not, it runs the same idempotent install command. This guarantees the agent never hits
`command not found` even if the skill is present but the CLI isn't.

## 5. Demo GIF

- Tool: `hyperframes` plugin (`github.com/heygen-com/hyperframes`). **Must be installed
  first** (implementation step).
- Storyboard (the real flow, not a mock): human types *"装一下 omnireach 然后帮我搜小红书
  上关于 X 的讨论"* → agent runs the one-line installer → agent runs
  `omnireach search --on xiaohongshu --json "…"` → results render. Capture the
  "one sentence, zero commands" promise visually.
- Output lands at repo root (e.g. `docs/assets/demo.gif`) and is embedded near the top of
  the README, under the tagline.

## 6. Deliverables

1. Rewritten **GitHub repo description** (one line, Senses/Eyes voice, English + 内含中文源).
2. Rewritten **README.md** — English-first, Chinese provided (either a `README.zh.md`
   companion or a bilingual layout; decide in plan). First screen = tagline + demo GIF +
   three pillars + AI-native install. Technical gate explainer + naming moved below fold.
3. **install.sh** at repo root — idempotent, non-interactive, self-contained; installs CLI
   + registers skill.
4. **SKILL.md** step-0 self-heal addition.
5. **docs/assets/demo.gif** + README embed.

## 7. Success criteria

- A stranger reading only the first README screen can state: what it is (eyes on the whole
  internet for an agent), the killer capability (login-walled vertical sources), and how to
  get it (tell your agent).
- `curl -fsSL <url> | sh` on a clean machine (no uv, no CLI) ends with a working
  `omnireach search "test"` and the skill discoverable by Claude Code — **verified by real
  E2E**, per project rule (mock/dry-run does not count as done).
- The installer runs to completion with **no interactive prompt** (agent-runnable),
  confirmed by piping with no TTY/stdin.
- Demo GIF plays the real ask-the-agent-to-install → vertical-search flow.

## 8. Open questions (resolve in plan / impl)

- Skill registration mechanism (a) vs (b) — §4.5, verify with `claude-code-guide`.
- Bilingual README layout: separate `README.zh.md` vs inline bilingual. (Lean separate file
  for an English-first first screen.)
- Does `install.sh` need a Windows/PowerShell sibling now, or defer (best-effort, per
  current platform posture)? Lean defer; note it.

## 9. Constraints honored

- Three-layer architecture boundary unchanged (no download/parse creep).
- Agent-first CLI UX preference (non-interactive, pipe-safe installer).
- "Real E2E before ship" rule applies to install.sh and the skill-registration path.
