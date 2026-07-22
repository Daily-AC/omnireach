"""omnireach CLI entry."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from omnireach import __version__
from omnireach.commands.check_update import check_update_cmd
from omnireach.commands.agy import agy_cmd
from omnireach.commands.bridge import bridge_cmd
from omnireach.commands.fetch import fetch_cmd
from omnireach.commands.init import init_cmd
from omnireach.commands.media import media_cmd
from omnireach.commands.setup import setup_cmd
from omnireach.commands.preferences import preferences_cmd
from omnireach.commands.sources import sources_cmd
from omnireach.registry import load_registry
from omnireach.secrets_env import load_secrets_env
from omnireach.service import augment_with_active_boosters, search

_SECRETS_PATH = Path.home() / ".omnireach" / "secrets.env"
load_secrets_env(_SECRETS_PATH)

ISSUE_URL = "https://github.com/Daily-AC/omnireach/issues/new/choose"

console = Console()


def _augment_with_active_boosters(source_ids, reg, explicit_sources):
    """Compatibility wrapper for callers that imported the former CLI helper."""
    return augment_with_active_boosters(source_ids, reg, explicit_sources)


def _should_emit_json(explicit_flag: bool) -> bool:
    """v0.9.2 + v0.10: explicit flag → JSON; OMNIREACH_FORCE_JSON=1 → JSON;
    else isatty-based detection.

    The env var is a v0.10 addition for Agent harnesses (e.g. Antigravity)
    that allocate a real PTY for subprocess stdout — isatty() returns True
    in those, defeating the v0.9.2 auto-JSON trick. Agents should set
    OMNIREACH_FORCE_JSON=1 once in their harness env.
    """
    if explicit_flag:
        return True
    if os.environ.get("OMNIREACH_FORCE_JSON", "").lower() in ("1", "true", "yes"):
        return True
    return not sys.stdout.isatty()


@click.group()
@click.version_option(__version__, "-V", "--version")
def main() -> None:
    """omnireach — 全网通搜索 CLI."""


@main.command("mcp")
def mcp_cmd() -> None:
    """Run the omnireach MCP server over stdio."""
    from omnireach.mcp_server import serve_stdio

    serve_stdio()


@main.command("search")
@click.argument("query")
@click.option(
    "--on", "--sources", "on_",
    help="只用这些源, 逗号分隔. 例: --on hackernews,web",
)
@click.option("--mode", type=click.Choice(["auto", "quick", "deep"]), default="auto")
@click.option("--limit", type=int, default=10, help="每个源最多返回多少条")
@click.option(
    "--timeout", type=click.FloatRange(min=1, max=120), default=None,
    help="显式覆盖所有源的 timeout (秒); heavy 源默认 60 秒",
)
@click.option(
    "--profile",
    help="选择 OpenCLI Browser Bridge profile (透传为 OPENCLI_PROFILE)",
)
@click.option("--json", "json_out", is_flag=True, help="输出 JSON, 适合下游 pipe")
def search_cmd(
    query: str,
    on_: str | None,
    mode: str,
    limit: int,
    timeout: float | None,
    profile: str | None,
    json_out: bool,
) -> None:
    """运行一次搜索."""
    explicit: list[str] | None = None
    if on_:
        requested = [source.strip() for source in on_.split(",") if source.strip()]
        known = {spec.id for spec in load_registry().sources}
        for unknown in [source for source in requested if source not in known]:
            click.echo(
                f"warning: 未知源 '{unknown}' — 跳过 "
                "(用 `omnireach sources` 查看可用源)",
                err=True,
            )
        explicit = [source for source in requested if source in known]
        if not explicit:
            raise click.UsageError("没有有效的 source")

    envelope = asyncio.run(
        search(
            query,
            sources=explicit,
            mode=mode,
            limit=limit,
            timeout=timeout,
            profile=profile,
        )
    )
    ranked = envelope.results
    errors = envelope.errors
    for error in errors:
        if error.error.startswith("adapter load failed:"):
            click.echo(f"skip {error.source}: {error.error}", err=True)

    if _should_emit_json(json_out):
        click.echo(envelope.model_dump_json())
        return

    table = Table(title=f"omnireach: {query}  ({len(ranked)} hits, {len(errors)} errors)")
    table.add_column("源", style="cyan")
    table.add_column("标题")
    table.add_column("URL", style="dim")
    for r in ranked:
        source_label = f"💎 {r.source}" if r.cost == "paid" else r.source
        table.add_row(source_label, r.title[:80], r.url)
    console.print(table)
    failed = [e for e in errors if e.category == "failed"]
    unavailable = [e for e in errors if e.category == "unavailable"]
    for err in failed:
        console.print(f"[red]✗ {err.source}: {err.error}[/red]")
    if failed:
        console.print(
            f"[dim]💬 觉得是 bug? 提 issue: {ISSUE_URL}[/dim]"
        )
    if unavailable:
        n = len(unavailable)
        console.print(f"[dim]ℹ️  {n} 个源未配置 (跑 `omnireach doctor` 查看修复建议)[/dim]")


@main.command("doctor")
@click.option("--json", "json_out", is_flag=True, help="输出 JSON, 适合下游 pipe")
def doctor_cmd(json_out: bool) -> None:
    """检查每个源 + fetch backend 的就绪状态."""
    import platform
    import json as _json

    from omnireach.doctor import (
        run_doctor,
        run_fetch_backend_doctor,
        run_media_backend_doctor,
        run_wechat_backend_doctor,
    )

    plat = f"{platform.system()} {platform.release()} ({platform.machine()})"
    pyver = f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    statuses = asyncio.run(run_doctor())
    fetch_backends = run_fetch_backend_doctor()
    media_backends = run_media_backend_doctor()
    wechat_backends = run_wechat_backend_doctor()

    if _should_emit_json(json_out):
        payload = {
            "omnireach_version": __version__,
            "python": pyver,
            "platform": plat,
            "sources": [
                {"id": s.id, "tier": s.tier, "ok": s.ok,
                 "detail": s.detail, "fix_hint": s.fix_hint}
                for s in statuses
            ],
            "fetch_backends": [
                {"tool": b.tool, "ok": b.ok,
                 "detail": b.detail, "fix_hint": b.fix_hint}
                for b in fetch_backends
            ],
            "media_backends": [
                {"tool": b.tool, "ok": b.ok,
                 "detail": b.detail, "fix_hint": b.fix_hint}
                for b in media_backends
            ],
            "wechat_backends": [
                {"tool": b.tool, "ok": b.ok,
                 "detail": b.detail, "fix_hint": b.fix_hint}
                for b in wechat_backends
            ],
        }
        click.echo(_json.dumps(payload, ensure_ascii=False))
        return

    console.print(f"[dim]omnireach {__version__} · {pyver} · {plat}[/dim]")
    table = Table(title="omnireach doctor — sources")
    table.add_column("源", style="cyan")
    table.add_column("tier")
    table.add_column("状态")
    table.add_column("说明", style="dim")
    table.add_column("修复")
    for s in statuses:
        icon = "✅" if s.ok else "❌"
        table.add_row(s.id, s.tier, icon, s.detail, s.fix_hint)
    console.print(table)

    # v0.9.3: separate panel for fetch backends (URL → 全文 工具, omnireach 自己不做)
    fb_table = Table(title="fetch backends — 把 search URL 拉成全文 (可选, 自动检测 PATH)")
    fb_table.add_column("工具", style="cyan")
    fb_table.add_column("状态")
    fb_table.add_column("说明", style="dim")
    fb_table.add_column("修复")
    for b in fetch_backends:
        icon = "✅" if b.ok else "❌"
        fb_table.add_row(b.tool, icon, b.detail, b.fix_hint)
    console.print(fb_table)

    media_table = Table(title="media backends — metadata + transcript parsing")
    media_table.add_column("工具", style="cyan")
    media_table.add_column("状态")
    media_table.add_column("说明", style="dim")
    media_table.add_column("修复")
    for b in media_backends:
        icon = "✅" if b.ok else "❌"
        media_table.add_row(b.tool, icon, b.detail, b.fix_hint)
    console.print(media_table)

    # v0.10.1: host-specific cookie-strategy backend for mp.weixin.qq.com
    wb_table = Table(title="wechat backends — mp.weixin.qq.com 登录态全文 (可选, 检测 OpenCLI + --stdout flag)")
    wb_table.add_column("工具", style="cyan")
    wb_table.add_column("状态")
    wb_table.add_column("说明", style="dim")
    wb_table.add_column("修复")
    for b in wechat_backends:
        icon = "✅" if b.ok else "❌"
        wb_table.add_row(b.tool, icon, b.detail, b.fix_hint)
    console.print(wb_table)


main.add_command(init_cmd)
main.add_command(agy_cmd)
main.add_command(bridge_cmd)
main.add_command(setup_cmd)
main.add_command(sources_cmd)
main.add_command(preferences_cmd)
main.add_command(check_update_cmd)
main.add_command(fetch_cmd)
main.add_command(media_cmd)


def _entrypoint() -> None:
    """Console-script wrapper that catches unhandled exceptions and points users at issues."""
    try:
        main.main(standalone_mode=False)
    except click.ClickException as exc:
        json_requested = "--json" in sys.argv[1:] or os.environ.get(
            "OMNIREACH_FORCE_JSON", ""
        ).lower() in ("1", "true", "yes")
        if json_requested:
            click.echo(json.dumps({
                "ok": False,
                "error": {
                    "type": "usage_error",
                    "message": exc.format_message(),
                    "exit_code": exc.exit_code,
                },
            }, ensure_ascii=False))
        else:
            exc.show()
        raise SystemExit(exc.exit_code)
    except click.exceptions.Exit as exc:
        raise SystemExit(exc.exit_code)
    except KeyboardInterrupt:
        console.print("\n[yellow]中断[/yellow]")
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001
        import traceback
        console.print(f"\n[red]omnireach 内部错误: {exc.__class__.__name__}: {exc}[/red]")
        console.print("[dim]" + traceback.format_exc() + "[/dim]")
        console.print(
            f"\n[bold]💬 请把上面这段 traceback + `omnireach --version` 一起提 issue:[/bold]\n   {ISSUE_URL}"
        )
        raise SystemExit(2)


if __name__ == "__main__":
    _entrypoint()
