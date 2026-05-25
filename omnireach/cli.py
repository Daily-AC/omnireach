"""omnireach CLI entry."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.table import Table

from omnireach import __version__
from omnireach.dispatcher import Dispatcher
from omnireach.normalizer import build_envelope
from omnireach.registry import load_registry
from omnireach.router import RouteRequest, Router
from omnireach.scorer import rank

console = Console()


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

    adapters = {}
    for sid in route.source_ids:
        try:
            spec = reg.get(sid)
            adapters[sid] = spec.load_adapter_class()()
        except Exception as e:  # noqa: BLE001
            click.echo(f"skip {sid}: {e}", err=True)

    dispatcher = Dispatcher(timeout=timeout, per_source_limit=limit)
    results, errors = asyncio.run(dispatcher.run(adapters, query))
    ranked = rank(results)
    envelope = build_envelope(query=query, results=ranked, errors=errors)

    if json_out:
        click.echo(envelope.model_dump_json())
        return

    table = Table(title=f"omnireach: {query}  ({len(ranked)} hits, {len(errors)} errors)")
    table.add_column("源", style="cyan")
    table.add_column("标题")
    table.add_column("URL", style="dim")
    for r in ranked:
        table.add_row(r.source, r.title[:80], r.url)
    console.print(table)
    for err in errors:
        console.print(f"[red]✗ {err.source}: {err.error}[/red]")


if __name__ == "__main__":
    main()
