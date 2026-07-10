"""Click rendering adapter for `omnireach fetch <url>`."""

from __future__ import annotations

import os
import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from omnireach.fetcher import (
    _fetch_via_crwl,
    _fetch_via_http,
    _fetch_via_jina,
    _fetch_via_opencli_weixin,
    _host_of,
    _looks_like_captcha,
    _resolve_backends,
    fetch,
)

console = Console()


def _should_emit_json(explicit_flag: bool) -> bool:
    """Return whether command output must use the machine-readable envelope."""
    if explicit_flag:
        return True
    if os.environ.get("OMNIREACH_FORCE_JSON", "").lower() in ("1", "true", "yes"):
        return True
    return not sys.stdout.isatty()


@click.command("fetch")
@click.argument("url")
@click.option(
    "--backend",
    type=click.Choice(["auto", "http", "jina", "crwl", "opencli"]),
    default="auto",
    help="auto = host-aware (mp.weixin.qq.com → opencli; else http → jina); 或显式指定",
)
@click.option("--json", "json_out", is_flag=True, help="输出 JSON envelope, 适合下游 pipe")
@click.option("--timeout", type=float, default=30.0, help="单 backend 超时秒数")
def fetch_cmd(url: str, backend: str, json_out: bool, timeout: float) -> None:
    """获取 URL 的全文 markdown."""
    result = fetch(url, backend=backend, timeout=timeout)

    if _should_emit_json(json_out):
        click.echo(result.model_dump_json())
        if not result.content_markdown:
            raise SystemExit(1)
        return

    if not result.content_markdown:
        for error in result.errors:
            console.print(f"[red]✗ {error}[/red]")
        raise SystemExit(1)

    console.print(Panel.fit(
        f"[cyan]{url}[/cyan]\n"
        f"[dim]backend: {result.backend} · fetched: {result.fetched_at} · "
        f"{len(result.content_markdown)} chars[/dim]",
        title="omnireach fetch",
    ))
    preview = result.content_markdown[:5000]
    if len(result.content_markdown) > 5000:
        preview += "\n\n…(truncated; 用 --json 拿完整内容)"
    console.print(Markdown(preview))


__all__ = [
    "_fetch_via_crwl",
    "_fetch_via_http",
    "_fetch_via_jina",
    "_fetch_via_opencli_weixin",
    "_host_of",
    "_looks_like_captcha",
    "_resolve_backends",
    "_should_emit_json",
    "fetch_cmd",
]
