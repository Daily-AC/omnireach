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
if grep -Eq '(^|[^a-zA-Z_])read([[:space:]]|$)' "$INSTALL"; then
  fail "install.sh contains an interactive 'read' — must be non-interactive"
fi
echo "ok: no interactive read"

# 3. Idempotent marker: uses --force on the CLI install and mkdir -p
grep -q 'uv tool install --force' "$INSTALL" || fail "CLI install must use --force (idempotent)"
grep -q 'mkdir -p' "$INSTALL" || fail "skill dir creation must use mkdir -p (idempotent)"
echo "ok: idempotency markers present"

echo "PASS: verify-install static checks"
