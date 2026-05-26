"""`omnireach preferences {show,edit,reset,path}`."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import click

from omnireach.preferences import (
    load_preferences,
    preferences_path,
    write_default_preferences,
)


@click.group("preferences")
def preferences_cmd() -> None:
    """查看/编辑用户偏好 (~/.omnireach/preferences.toml)."""


@preferences_cmd.command("path")
def _path() -> None:
    click.echo(str(preferences_path()))


@preferences_cmd.command("show")
def _show() -> None:
    p = load_preferences()
    click.echo(json.dumps(p.model_dump(), indent=2, ensure_ascii=False))


def _default_editor() -> str | None:
    """Resolve a sensible editor: $EDITOR → platform default."""
    env_editor = os.environ.get("EDITOR")
    if env_editor:
        return env_editor
    if os.name == "nt":
        # Windows: notepad is always present; fallback notepad++ if installed
        for candidate in ("notepad++", "notepad.exe", "notepad"):
            if shutil.which(candidate):
                return candidate
        return "notepad"  # always exists on Windows even if not on PATH lookup
    # POSIX
    for candidate in ("nano", "vim", "vi"):
        if shutil.which(candidate):
            return candidate
    return None


@preferences_cmd.command("edit")
def _edit() -> None:
    path = preferences_path()
    if not path.exists():
        write_default_preferences(path)
    editor = _default_editor()
    if not editor:
        click.echo("找不到 $EDITOR / vi / nano / notepad，直接编辑文件吧:", err=True)
        click.echo(str(path), err=True)
        return
    subprocess.call([editor, str(path)])


@preferences_cmd.command("reset")
def _reset() -> None:
    path = preferences_path()
    if path.exists():
        backup = path.with_suffix(".toml.bak")
        shutil.copy2(path, backup)
        click.echo(f"已备份到 {backup}")
    write_default_preferences(path)
    click.echo(f"已写入默认配置到 {path}")
