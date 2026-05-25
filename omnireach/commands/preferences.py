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


@preferences_cmd.command("edit")
def _edit() -> None:
    path = preferences_path()
    if not path.exists():
        write_default_preferences(path)
    editor = os.environ.get("EDITOR") or ("vi" if shutil.which("vi") else "")
    if not editor:
        click.echo("没有 $EDITOR 也没有 vi，直接编辑文件吧:", err=True)
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
