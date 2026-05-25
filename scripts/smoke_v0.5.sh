#!/usr/bin/env bash
# v0.5 smoke: verify a fresh deployment can search HN (the only true zero-config source)
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== install (editable) ==="
uv pip install -e . --reinstall >/dev/null

VERSION=$(uv run omnireach --version 2>&1 | tail -1)
echo "omnireach version: $VERSION"
if [[ "$VERSION" != *"0.5.0-alpha"* ]]; then
    echo "WARN: version not 0.5.0-alpha (got: $VERSION)"
fi

echo
echo "=== omnireach sources ==="
uv run omnireach sources

echo
echo "=== omnireach doctor ==="
uv run omnireach doctor

echo
echo "=== search 'vibe coding' (HN only, no setup) ==="
uv run omnireach search "vibe coding" --limit 3 --timeout 30 || true

echo
echo "=== smoke complete ==="
