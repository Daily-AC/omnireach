#!/usr/bin/env bash
# Recordable proof that read-only MCP calls avoid visible browser windows.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

URL="${OMNIREACH_DEMO_URL:-https://www.rfc-editor.org/rfc/rfc9110.html}"

chrome_window_count() {
    if [[ "$(uname -s)" != "Darwin" ]] || ! pgrep -x "Google Chrome" >/dev/null; then
        printf '0\n'
        return
    fi
    osascript -e 'tell application "Google Chrome" to count windows'
}

before="$(chrome_window_count)"
printf 'Chrome windows before: %s\n\n' "$before"

printf '1. omnireach_fetch through the real MCP server\n'
request="$(jq -nc --arg url "$URL" '{
  jsonrpc: "2.0",
  id: 1,
  method: "tools/call",
  params: {
    name: "omnireach_fetch",
    arguments: {url: $url, backend: "http", timeout: 60}
  }
}')"
response="$(printf '%s\n' "$request" | uv run omnireach mcp)"
printf '%s\n' "$response" | jq -er '
  select(.result.isError == false)
  | .result.structuredContent
  | "   backend=\(.backend), markdown=\(.content_markdown | length) chars"
'

if [[ "${OMNIREACH_DEMO_SKIP_XHS:-0}" != "1" ]]; then
    printf '\n2. Logged-in Xiaohongshu search through the silent Chrome bridge\n'
    uv run omnireach search \
        --on xiaohongshu \
        --limit 3 \
        --json \
        "Claude Code 浏览器自动化" \
        | jq -er '
            select((.errors | length) == 0 and (.results | length) > 0)
            | "   results=\(.results | length), first=\(.results[0].title[0:64])"
        '
fi

after="$(chrome_window_count)"
printf '\nChrome windows after:  %s\n' "$after"
if [[ "$before" != "$after" ]]; then
    printf 'Visible Chrome window count changed: %s -> %s\n' "$before" "$after" >&2
    exit 1
fi
printf 'No visible Chrome window was added.\n'
