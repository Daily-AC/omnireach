"""omnireach init — write default preferences + show next-step guidance.

v0.5+ note: Agent-Reach is fully optional (runtime never invokes it).
v0.6.1: init no longer attempts to `pipx install agent-reach` — it's just config bootstrap.
"""

from __future__ import annotations

import click
from rich.console import Console

from omnireach.preferences import preferences_path, write_default_preferences

console = Console()


def _write_default_prefs_if_missing() -> bool:
    pref_path = preferences_path()
    if pref_path.exists():
        return False
    write_default_preferences(pref_path)
    click.echo(f"  ✅ 已写入默认偏好: {pref_path}")
    return True


@click.command("init")
@click.option("--yes", "-y", is_flag=True, help="(已弃用) 保留为兼容旧脚本; init 不再有交互步骤")
def init_cmd(yes: bool) -> None:
    """初始化用户配置 (写默认 preferences.toml + 打印源解锁指引)."""
    wrote = _write_default_prefs_if_missing()
    if not wrote:
        click.echo(f"  ✅ 偏好已存在: {preferences_path()}")

    console.print()
    console.print("[bold]✨ omnireach 已就绪[/bold]")
    console.print("零配置可用: [cyan]hackernews[/cyan] · [cyan]rss[/cyan]")
    console.print()
    console.print("下一步:")
    console.print("  [bold]omnireach sources[/bold]       — 查看所有源 + 当前可用状态")
    console.print("  [bold]omnireach doctor[/bold]        — 体检各源 (binary / API Key)")
    console.print("  [bold]omnireach setup <源名>[/bold]   — 解锁单个源 (例: setup youtube / setup tavily)")
    console.print()
    console.print("立即试试: [bold]omnireach search \"vibe coding\"[/bold]")
