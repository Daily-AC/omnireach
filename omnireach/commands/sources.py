"""omnireach sources — list registered sources grouped by tier."""

from __future__ import annotations

import asyncio
import json as _json
import os
import sys

import click
from rich.console import Console
from rich.table import Table

from omnireach.doctor import run_doctor
from omnireach.registry import load_registry


def _should_emit_json(explicit_flag: bool) -> bool:
    """v0.9.2 same helper as cli.py — auto-JSON for Agent callers."""
    if explicit_flag:
        return True
    return not sys.stdout.isatty()

console = Console()

TIER_ICON = {
    "ready": "✅",
    "one_step": "🟡",
    "heavy": "🔴",
    "booster": "💎",
    "wip": "🚧",
}
TIER_LABEL = {
    "ready": "ready",
    "one_step": "one_step",
    "heavy": "heavy",
    "booster": "付费增强",
    "wip": "v0.6 重写中",
}

BOOSTER_KEY_ENV = {
    "tavily": "TAVILY_API_KEY",
    "brave": "BRAVE_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "exa": "EXA_API_KEY",
}


def _booster_key_status(source_id: str) -> str:
    """Return ' (✓ 已配)' if the booster env var is set, else ' (未配)'."""
    env_var = BOOSTER_KEY_ENV.get(source_id)
    if env_var and os.environ.get(env_var):
        return " (✓ 已配)"
    return " (未配)"


@click.command("sources")
@click.option("--probe", is_flag=True, help="实际跑 is_ready 探测每个源 (慢一点)")
@click.option("--json", "json_out", is_flag=True, help="输出 JSON, 适合下游 pipe")
def sources_cmd(probe: bool, json_out: bool) -> None:
    """列出所有源 + 心愿单状态."""
    reg = load_registry()

    statuses: dict[str, bool] = {}
    if probe:
        for s in asyncio.run(run_doctor()):
            statuses[s.id] = s.ok

    if _should_emit_json(json_out):
        payload = {
            "sources": [
                {
                    "id": s.id,
                    "tier": s.tier,
                    "description": s.description,
                    "enhanced_with": s.enhanced_with,
                    "probe_ok": statuses.get(s.id) if probe else None,
                }
                for s in reg.sources
            ],
            "probed": probe,
        }
        click.echo(_json.dumps(payload, ensure_ascii=False))
        return

    by_tier: dict[str, list] = {
        "ready": [],
        "one_step": [],
        "heavy": [],
        "wip": [],
        "booster": [],
    }
    for s in reg.sources:
        by_tier.setdefault(s.tier, []).append(s)

    for tier in ["ready", "one_step", "heavy", "wip", "booster"]:
        items = by_tier.get(tier, [])
        if not items:
            continue
        label = TIER_LABEL.get(tier, tier)
        table = Table(title=f"{TIER_ICON[tier]} {label} ({len(items)})", show_lines=False)
        table.add_column("id", style="cyan")
        table.add_column("描述")
        if probe:
            table.add_column("probe")
        for s in items:
            sid = s.id
            if tier == "booster":
                sid = f"{s.id}{_booster_key_status(s.id)}"
            elif tier == "wip":
                sid = f"{s.id} (待实现)"
            row = [sid, s.description]
            if probe:
                row.append("✅" if statuses.get(s.id) else "❌")
            table.add_row(*row)
        console.print(table)
