"""Install the packaged native Chrome extension into a stable user directory."""

from __future__ import annotations

import json
import secrets
import stat
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True)
class BridgePaths:
    root: Path
    extension_dir: Path
    token_path: Path


def bridge_paths(*, home: Path | None = None) -> BridgePaths:
    root = (home or Path.home()) / ".omnireach"
    return BridgePaths(
        root=root,
        extension_dir=root / "chrome-extension",
        token_path=root / "bridge-token",
    )


def bridge_configured(*, home: Path | None = None) -> bool:
    paths = bridge_paths(home=home)
    return (
        paths.token_path.is_file()
        and (paths.extension_dir / "manifest.json").is_file()
        and (paths.extension_dir / "bridge-config.js").is_file()
    )


def _load_or_create_token(paths: BridgePaths) -> str:
    if paths.token_path.exists():
        token = paths.token_path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    paths.token_path.write_text(token + "\n", encoding="utf-8")
    paths.token_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return token


def install_extension(*, home: Path | None = None) -> BridgePaths:
    paths = bridge_paths(home=home)
    paths.extension_dir.mkdir(parents=True, exist_ok=True)
    token = _load_or_create_token(paths)

    asset_root = files("omnireach.chrome_extension")
    for asset in asset_root.iterdir():
        if not asset.is_file() or asset.name in {
            "__init__.py",
            "bridge-config.example.js",
        }:
            continue
        (paths.extension_dir / asset.name).write_bytes(asset.read_bytes())

    config = {
        "baseUrl": "http://127.0.0.1:19826",
        "token": token,
    }
    config_json = json.dumps(config, ensure_ascii=True, separators=(",", ":"))
    (paths.extension_dir / "bridge-config.js").write_text(
        "globalThis.OMNIREACH_BRIDGE_CONFIG = Object.freeze("
        + config_json
        + ");\n",
        encoding="utf-8",
    )
    return paths
