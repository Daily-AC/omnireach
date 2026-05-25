"""Installer — auto-install upstream tools the Agent can handle without user input."""

from __future__ import annotations

import shutil
import subprocess


class InstallError(Exception):
    def __init__(self, package: str, reason: str, *, hint: str | None = None) -> None:
        super().__init__(f"install {package} failed: {reason}")
        self.package = package
        self.reason = reason
        self.hint = hint


def ensure_binary(name: str, *, hint: str | None = None) -> str:
    """Return absolute path to a binary on PATH, or raise."""
    path = shutil.which(name)
    if not path:
        raise InstallError(name, f"binary '{name}' not on PATH", hint=hint)
    return path


def install_pipx_package(package: str) -> None:
    ensure_binary("pipx", hint="安装 pipx: brew install pipx 或 python -m pip install --user pipx")
    res = subprocess.run(
        ["pipx", "install", package],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise InstallError(package, res.stderr or res.stdout or "pipx install failed")


def install_npm_global(package: str) -> None:
    ensure_binary("npm", hint="安装 Node.js (>=20): https://nodejs.org/")
    res = subprocess.run(
        ["npm", "install", "-g", package],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise InstallError(package, res.stderr or "npm install -g failed")
