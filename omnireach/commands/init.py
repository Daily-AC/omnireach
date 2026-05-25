"""omnireach init — install zero-config upstream dependencies."""

from __future__ import annotations

import shutil

import click
from rich.console import Console

from omnireach import installer
from omnireach.preferences import preferences_path, write_default_preferences

console = Console()


def _write_default_prefs_if_missing() -> None:
    pref_path = preferences_path()
    if not pref_path.exists():
        write_default_preferences(pref_path)
        click.echo(f"  ✅ 已写入默认偏好: {pref_path}")


@click.command("init")
@click.option("--yes", "-y", is_flag=True, help="跳过确认")
def init_cmd(yes: bool) -> None:
    """安装零配置源所需的上游工具 (主要是 agent-reach)."""
    _write_default_prefs_if_missing()

    if shutil.which("agent-reach"):
        console.print("[green]✅ agent-reach 已安装[/green]")
        return

    if not yes:
        try:
            proceed = click.confirm("即将通过 pipx 安装 agent-reach (Agent-Reach), 继续?")
        except click.exceptions.Abort:
            proceed = False
        if not proceed:
            console.print("[yellow]取消[/yellow]")
            return

    console.print("[cyan]正在 pipx install agent-reach…[/cyan]")
    try:
        installer.install_pipx_package("agent-reach")
    except installer.InstallError as e:
        console.print(f"[red]安装失败: {e}[/red]")
        if e.hint:
            console.print(f"[yellow]提示: {e.hint}[/yellow]")
        raise SystemExit(1)
    console.print("[green]✅ agent-reach 安装完成[/green]")
    console.print("现在试试: [bold]omnireach \"Claude 4.7 怎么样\"[/bold]")
