"""Install and inspect the Omnireach native Chrome bridge."""

from __future__ import annotations

import json

import click

from omnireach.bridge_install import (
    bridge_configured,
    bridge_paths,
    install_extension,
)
from omnireach.native_bridge import (
    NativeBridgeCommandError,
    NativeBridgeUnavailable,
    probe_native_bridge,
    request_extension_reload,
)

RELOAD_POLL_SECONDS = 20.0


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
@click.option(
    "--rotate-token",
    is_flag=True,
    help="轮换本机 bridge token，使旧 Chrome profile 立即失效",
)
def bridge_install_cmd(json_out: bool, rotate_token: bool) -> None:
    paths = install_extension(rotate_token=rotate_token)
    _emit(
        {
            "installed": True,
            "extension_dir": str(paths.extension_dir),
            "load_unpacked": str(paths.extension_dir),
            "token_rotated": rotate_token,
        },
        json_out,
    )


@bridge_cmd.command("reload")
@click.option("--json", "json_out", is_flag=True, help="输出 JSON")
@click.option(
    "--timeout",
    type=click.FloatRange(min=5, max=120),
    default=RELOAD_POLL_SECONDS,
    show_default=True,
    help="等待扩展带着新版本重新连上的秒数",
)
def bridge_reload_cmd(json_out: bool, timeout: float) -> None:
    """让已连接的扩展自己重载, 免去手动去 chrome://extensions 点按钮."""
    import time

    paths = bridge_paths()
    manifest_path = paths.extension_dir / "manifest.json"
    installed = None
    if manifest_path.is_file():
        try:
            installed = json.loads(
                manifest_path.read_text(encoding="utf-8")
            ).get("version")
        except (OSError, json.JSONDecodeError):
            installed = None

    try:
        request_extension_reload()
    except NativeBridgeCommandError as exc:
        _emit(
            {
                "reloaded": False,
                "error": (
                    f"{exc}; 这个扩展版本还没有 system.reload —— "
                    "这一次仍需去 chrome://extensions 手动重载"
                ),
            },
            json_out,
        )
        raise click.exceptions.Exit(1)
    except NativeBridgeUnavailable as exc:
        _emit({"reloaded": False, "error": str(exc)}, json_out)
        raise click.exceptions.Exit(1)

    deadline = time.monotonic() + timeout
    connected = None
    while time.monotonic() < deadline:
        try:
            connected = probe_native_bridge().get("extensionVersion")
        except (NativeBridgeUnavailable, NativeBridgeCommandError):
            connected = None
        if connected and (installed is None or connected == installed):
            _emit(
                {
                    "reloaded": True,
                    "installed_version": installed,
                    "connected_version": connected,
                },
                json_out,
            )
            return
        time.sleep(0.5)

    _emit(
        {
            "reloaded": False,
            "installed_version": installed,
            "connected_version": connected,
            "error": (
                "扩展没有在超时前带着新版本重新连上; "
                "去 chrome://extensions 手动重载一次"
            ),
        },
        json_out,
    )
    raise click.exceptions.Exit(1)


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
    installed_version = None
    manifest_path = paths.extension_dir / "manifest.json"
    if manifest_path.is_file():
        try:
            installed_version = json.loads(
                manifest_path.read_text(encoding="utf-8")
            ).get("version")
        except (OSError, json.JSONDecodeError):
            pass
    connected = False
    error = ""
    details: dict[str, object] = {}
    if configured:
        try:
            details = probe_native_bridge()
            connected = True
        except (NativeBridgeUnavailable, NativeBridgeCommandError) as exc:
            error = str(exc)
    _emit(
        {
            "installed": configured,
            "connected": connected,
            "extension_dir": str(paths.extension_dir),
            "installed_version": installed_version,
            "connected_version": details.get("extensionVersion"),
            "extension_version": details.get("extensionVersion"),
            "commands": details.get("commands", []),
            "reload_required": bool(
                connected
                and installed_version
                and installed_version != details.get("extensionVersion")
            ),
            "error": error,
        },
        json_out,
    )
