"""omnireach CLI entry."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from omnireach import __version__
from omnireach.commands.check_update import check_update_cmd
from omnireach.commands.init import init_cmd
from omnireach.commands.setup import setup_cmd
from omnireach.commands.preferences import preferences_cmd
from omnireach.commands.sources import sources_cmd
from omnireach.dispatcher import Dispatcher
from omnireach.normalizer import build_envelope
from omnireach.registry import load_registry
from omnireach.router import RouteRequest, Router
from omnireach.scorer import rank
from omnireach.secrets_env import load_secrets_env

_SECRETS_PATH = Path.home() / ".omnireach" / "secrets.env"
load_secrets_env(_SECRETS_PATH)

console = Console()


_BOOSTER_KEY_ENV = {
    "tavily": "TAVILY_API_KEY",
    "brave": "BRAVE_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "exa": "EXA_API_KEY",
}


def _augment_with_active_boosters(source_ids, reg, explicit_sources):
    """When a booster's API Key env is set, ensure it's in the fanout.

    Only auto-augments when user didn't pass --on (explicit overrides win).
    """
    if explicit_sources:
        return source_ids
    out = list(source_ids)
    for booster_id, env in _BOOSTER_KEY_ENV.items():
        if not os.environ.get(env):
            continue
        if booster_id in out:
            continue
        try:
            reg.get(booster_id)
        except KeyError:
            continue
        out.append(booster_id)
    return out


@click.group()
@click.version_option(__version__, "-V", "--version")
def main() -> None:
    """omnireach — 全网通搜索 CLI."""


@main.command("search")
@click.argument("query")
@click.option("--on", "on_", help="只用这些源, 逗号分隔. 例: --on hackernews,web")
@click.option("--mode", type=click.Choice(["auto", "quick", "deep"]), default="auto")
@click.option("--limit", type=int, default=10, help="每个源最多返回多少条")
@click.option("--timeout", type=float, default=15.0)
@click.option("--json", "json_out", is_flag=True, help="输出 JSON, 适合下游 pipe")
def search_cmd(query: str, on_: str | None, mode: str, limit: int, timeout: float, json_out: bool) -> None:
    """运行一次搜索."""
    explicit = [s.strip() for s in on_.split(",")] if on_ else None
    reg = load_registry()
    router = Router(reg)
    route = router.plan(RouteRequest(query=query, explicit_sources=explicit, mode=mode))

    for unknown in route.unknown_sources:
        click.echo(f"warning: 未知源 '{unknown}' — 跳过 (用 `omnireach sources` 查看可用源)", err=True)

    route_sources = _augment_with_active_boosters(route.source_ids, reg, explicit)

    adapters = {}
    for sid in route_sources:
        try:
            spec = reg.get(sid)
            adapters[sid] = spec.load_adapter_class()()
        except Exception as e:  # noqa: BLE001
            click.echo(f"skip {sid}: {e}", err=True)

    dispatcher = Dispatcher(timeout=timeout, per_source_limit=limit)
    results, errors = asyncio.run(dispatcher.run(adapters, query))
    trust_map = {s.id: s.trust for s in reg.sources}
    ranked = rank(results, trust_map=trust_map)
    envelope = build_envelope(query=query, results=ranked, errors=errors)

    if json_out:
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
    for err in errors:
        console.print(f"[red]✗ {err.source}: {err.error}[/red]")


@main.command("doctor")
def doctor_cmd() -> None:
    """检查每个源的就绪状态."""
    from omnireach.doctor import run_doctor

    statuses = asyncio.run(run_doctor())
    table = Table(title="omnireach doctor")
    table.add_column("源", style="cyan")
    table.add_column("tier")
    table.add_column("状态")
    table.add_column("说明", style="dim")
    table.add_column("修复")
    for s in statuses:
        icon = "✅" if s.ok else "❌"
        table.add_row(s.id, s.tier, icon, s.detail, s.fix_hint)
    console.print(table)


main.add_command(init_cmd)
main.add_command(setup_cmd)
main.add_command(sources_cmd)
main.add_command(preferences_cmd)
main.add_command(check_update_cmd)

if __name__ == "__main__":
    main()
