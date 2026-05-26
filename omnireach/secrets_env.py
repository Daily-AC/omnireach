"""dotenv-style loader for ~/.omnireach/secrets.env.

Intentionally minimal: KEY=VALUE per line, quotes stripped, comments skipped,
existing env wins. Avoids python-dotenv dependency.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path


def load_secrets_env(path: Path) -> None:
    """Read path and merge into os.environ (without overriding existing keys)."""
    if not path.exists():
        return

    # POSIX permission check; on Windows mode bits don't map to chmod semantics
    if os.name != "nt":
        try:
            mode = path.stat().st_mode
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                print(
                    f"warning: {path} permissions are loose ({oct(mode & 0o777)}); "
                    "请运行 `chmod 600` 限制可读权限",
                    file=sys.stderr,
                )
        except OSError:
            pass

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
