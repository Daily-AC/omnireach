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
fi

# Ensure uv's tool-bin dir is on PATH for THIS session — covers both the
# just-installed uv and the omnireach CLI we're about to install.
# uv installs to ~/.local/bin; ~/.cargo/bin kept as a harmless fallback.
for d in "${HOME}/.local/bin" "${HOME}/.cargo/bin"; do
  if [ -d "$d" ]; then PATH="$d:$PATH"; fi
done
export PATH

# 2. Install / update the CLI (force = idempotent: re-running pulls latest).
if ! command -v git >/dev/null 2>&1; then
  say "error: git is required to install omnireach. Install git and re-run."
  exit 1
fi
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
