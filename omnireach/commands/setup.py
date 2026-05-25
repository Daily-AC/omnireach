"""omnireach setup <source> — conversational setup wizard."""

from __future__ import annotations

import asyncio
import stat
import subprocess
from pathlib import Path

import click
from rich.console import Console

from omnireach import installer, wizard
from omnireach.registry import Dep, load_registry
from omnireach.wizard import StepKind, StepStatus

console = Console()


BOOSTER_GUIDES = {
    "tavily": {
        "env": "TAVILY_API_KEY",
        "signup_url": "https://tavily.com",
        "label": "Tavily Search API",
        "note": "免费层每月 1000 次查询",
    },
    "brave": {
        "env": "BRAVE_API_KEY",
        "signup_url": "https://brave.com/search/api",
        "label": "Brave Search API",
        "note": "免费层每月 2000 次查询",
    },
    "perplexity": {
        "env": "PERPLEXITY_API_KEY",
        "signup_url": "https://perplexity.ai/settings/api",
        "label": "Perplexity Sonar",
        "note": "按 token 计费 (sonar-pro)",
    },
}


def _setup_booster(source_id: str) -> None:
    g = BOOSTER_GUIDES[source_id]
    click.echo(f"{g['label']} 是付费 API ({g['note']})")
    click.echo("Agent 能做的:")
    click.echo("  ✅ 把你粘贴的 Key 写入 ~/.omnireach/secrets.env (chmod 600)")
    click.echo("你需要做的:")
    click.echo(f"  👤 去 {g['signup_url']} 注册/登录, 复制 API Key")
    if not click.confirm("开始吗?", default=True):
        return
    key = click.prompt(f"粘贴 {g['env']}", hide_input=True).strip()
    if not key:
        click.echo("空 Key, 取消", err=True)
        return
    secrets_path = Path.home() / ".omnireach" / "secrets.env"
    secrets_path.parent.mkdir(parents=True, exist_ok=True)
    existing = secrets_path.read_text() if secrets_path.exists() else ""
    lines = [ln for ln in existing.splitlines() if not ln.startswith(f"{g['env']}=")]
    lines.append(f"{g['env']}={key}")
    secrets_path.write_text("\n".join(lines) + "\n")
    secrets_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    click.echo(f"✓ 已写入 {secrets_path}")


def _confirm_factory(yes: bool):
    def confirm(msg: str) -> bool:
        if yes:
            return True
        return click.confirm(msg, default=True)

    return confirm


def _run_install(kind: str, name: str) -> None:
    if kind == "pipx":
        installer.install_pipx_package(name)
    elif kind == "npm":
        installer.install_npm_global(name)
    else:
        raise installer.InstallError(name, f"unknown install kind '{kind}'")


def _prompt_user_step_factory(yes: bool):
    def prompt(step: Dep) -> None:
        console.print(f"[bold yellow]👤 你需要做的:[/bold yellow] {step.step}")
        if not yes:
            click.prompt("做完按回车继续", default="", show_default=False)

    return prompt


def _run_verify(cmd: str) -> tuple[int, str]:
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.returncode, (res.stdout or "") + (res.stderr or "")


@click.command("setup")
@click.argument("source_id")
@click.option("--yes", "-y", is_flag=True, help="跳过所有确认 (CI / 自动化)")
def setup_cmd(source_id: str, yes: bool) -> None:
    """配置一个源 (装上游工具 + 引导用户登录)."""
    reg = load_registry()
    try:
        spec = reg.get(source_id)
    except KeyError:
        click.echo(f"未知源 '{source_id}'. 可用源: 跑 `omnireach sources`", err=True)
        raise SystemExit(2)

    if source_id in BOOSTER_GUIDES:
        _setup_booster(source_id)
        return

    adapter = spec.load_adapter_class()()
    report = asyncio.run(
        wizard.run_setup(
            spec,
            adapter=adapter,
            confirm=_confirm_factory(yes),
            run_install=_run_install,
            prompt_user_step=_prompt_user_step_factory(yes),
            run_verify=_run_verify,
        )
    )

    if report.already_ready:
        console.print(f"[green]✅ {source_id} 已就绪, 无需配置[/green]")
        return

    if report.aborted:
        console.print(f"[yellow]取消配置 {source_id}[/yellow]")
        raise SystemExit(1)

    icon = {StepStatus.OK: "✅", StepStatus.FAILED: "❌", StepStatus.SKIPPED: "⏭️"}
    for step in report.steps:
        kind_label = {StepKind.AUTO: "[Agent]", StepKind.MANUAL: "[你]", StepKind.VERIFY: "[验证]"}[step.kind]
        line = f"{icon[step.status]} {kind_label} {step.label}"
        if step.detail:
            line += f" — {step.detail}"
        console.print(line)

    if report.success:
        console.print(f"[green]✅ {source_id} 配置完成[/green]")
    else:
        console.print(f"[red]❌ {source_id} 配置失败[/red]")
        raise SystemExit(1)
