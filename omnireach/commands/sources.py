"""omnireach sources — list registered sources grouped by tier."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.table import Table

from omnireach.doctor import run_doctor
from omnireach.registry import load_registry

console = Console()

TIER_ICON = {"ready": "✅", "one_step": "🟡", "heavy": "🔴"}


@click.command("sources")
@click.option("--probe", is_flag=True, help="实际跑 is_ready 探测每个源 (慢一点)")
def sources_cmd(probe: bool) -> None:
    """列出所有源 + 心愿单状态."""
    reg = load_registry()

    statuses: dict[str, bool] = {}
    if probe:
        for s in asyncio.run(run_doctor()):
            statuses[s.source] = s.ok

    by_tier: dict[str, list] = {"ready": [], "one_step": [], "heavy": []}
    for s in reg.sources:
        by_tier.setdefault(s.tier, []).append(s)

    for tier in ["ready", "one_step", "heavy"]:
        items = by_tier.get(tier, [])
        if not items:
            continue
        table = Table(title=f"{TIER_ICON[tier]} {tier} ({len(items)})", show_lines=False)
        table.add_column("id", style="cyan")
        table.add_column("描述")
        if probe:
            table.add_column("probe")
        for s in items:
            row = [s.id, s.description]
            if probe:
                row.append("✅" if statuses.get(s.id) else "❌")
            table.add_row(*row)
        console.print(table)
