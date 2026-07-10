"""Install and inspect the Omnireach native Chrome bridge."""

from __future__ import annotations

import json

import click

from omnireach.bridge_install import (
    bridge_configured,
    bridge_paths,
    install_extension,
)


def _emit(payload: dict[str, object], json_out: bool) -> None:
    if json_out:
        click.echo(json.dumps(payload, ensure_ascii=False))
        return
    for key, value in payload.items():
        click.echo(f"{key}: {value}")


@click.group("bridge")
def bridge_cmd() -> None:
    """Manage the Omnireach native Chrome extension bridge."""


@bridge_cmd.command("install")
@click.option("--json", "json_out", is_flag=True, help="输出 JSON")
def bridge_install_cmd(json_out: bool) -> None:
    paths = install_extension()
    _emit(
        {
            "installed": True,
            "extension_dir": str(paths.extension_dir),
            "load_unpacked": str(paths.extension_dir),
        },
        json_out,
    )


@bridge_cmd.command("path")
@click.option("--json", "json_out", is_flag=True, help="输出 JSON")
def bridge_path_cmd(json_out: bool) -> None:
    paths = bridge_paths()
    _emit(
        {
            "configured": bridge_configured(),
            "extension_dir": str(paths.extension_dir),
        },
        json_out,
    )


@bridge_cmd.command("status")
@click.option("--json", "json_out", is_flag=True, help="输出 JSON")
def bridge_status_cmd(json_out: bool) -> None:
    paths = bridge_paths()
    configured = bridge_configured()
    _emit(
        {
            "installed": configured,
            "connected": False,
            "extension_dir": str(paths.extension_dir),
        },
        json_out,
    )
