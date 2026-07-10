#!/usr/bin/env bash
# verify-adapter-contracts.sh
# Checks each adapter's CLI argv shape against the upstream binary's --help.
# Skips checks for binaries not installed.
# Exits 0 if all installed binaries match their adapter's argv, 1 otherwise.
#
# Run this manually before each release candidate. Not run in CI (CI doesn't
# have all binaries installed).

set -uo pipefail

declare -A ADAPTERS=(
    ["yt-dlp:ytsearch"]="--flat-playlist --dump-json --no-warnings"
    ["gh:search repos"]="--json"
    ["gh:search issues"]="--json"
    ["opencli:reddit search"]="--format --limit --window --site-session --keep-tab"
    ["opencli:twitter search"]="--format --limit --window --site-session --keep-tab"
    ["opencli:xiaohongshu search"]="--format --limit --window --site-session --keep-tab"
    ["opencli:tiktok search"]="--format --limit --window --site-session --keep-tab"
    ["opencli:douyin search"]="--format --limit --window --site-session --keep-tab"
)

EXIT=0

for key in "${!ADAPTERS[@]}"; do
    binary="${key%%:*}"
    subcmd="${key#*:}"
    flags="${ADAPTERS[$key]}"
    if ! command -v "$binary" >/dev/null 2>&1; then
        echo "⏭️  $binary not installed, skipping ($subcmd)"
        continue
    fi
    # shellcheck disable=SC2086
    help_out=$("$binary" $subcmd --help 2>&1 || true)
    bad=()
    for flag in $flags; do
        if ! echo "$help_out" | grep -q -- "$flag"; then
            bad+=("$flag")
        fi
    done
    if [[ ${#bad[@]} -gt 0 ]]; then
        echo "❌ $binary $subcmd: missing flags: ${bad[*]}"
        EXIT=1
    else
        echo "✅ $binary $subcmd: argv OK"
    fi
done

exit $EXIT
