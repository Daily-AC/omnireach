"""CLI command for listing one creator's own works."""

from __future__ import annotations

import asyncio
import os
import sys

import click
from rich.console import Console
from rich.table import Table

from omnireach.author import AUTHOR_SOURCES, MAX_AUTHOR_LIMIT, author_catalog

console = Console()


def _emit_json(explicit: bool) -> bool:
    forced = os.environ.get("OMNIREACH_FORCE_JSON", "").lower() in {"1", "true", "yes"}
    return explicit or forced or not sys.stdout.isatty()


@click.command("author")
@click.argument("handle")
@click.option(
    "--source",
    type=click.Choice(list(AUTHOR_SOURCES)),
    default="douyin",
    show_default=True,
    help="哪个源提供作者目录",
)
@click.option(
    "--limit",
    type=click.IntRange(min=1, max=MAX_AUTHOR_LIMIT),
    default=20,
    show_default=True,
    help="返回多少条作品",
)
@click.option(
    "--order",
    type=click.Choice(["recent", "likes"]),
    default="recent",
    show_default=True,
    help="recent 只翻到够数; likes 必须扫完整个目录再排序",
)
@click.option(
    "--include-media-urls",
    is_flag=True,
    help="附带会过期的 CDN 直链 (raw.play_url), 用于绕开 yt-dlp",
)
@click.option(
    "--timeout",
    type=click.FloatRange(min=5, max=600),
    default=180,
    show_default=True,
    help="整个目录抓取的墙钟预算 (秒)",
)
@click.option("--json", "json_out", is_flag=True, help="输出 JSON, 适合下游 pipe")
def author_cmd(
    handle: str,
    source: str,
    limit: int,
    order: str,
    include_media_urls: bool,
    timeout: float,
    json_out: bool,
) -> None:
    """列出某个创作者本人发布的作品 (HANDLE 可以是昵称或主页 URL)."""
    try:
        envelope = asyncio.run(
            author_catalog(
                handle,
                source=source,
                limit=limit,
                order=order,
                include_media_urls=include_media_urls,
                timeout=timeout,
            )
        )
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    if _emit_json(json_out):
        click.echo(envelope.model_dump_json())
    else:
        author = envelope.author
        title = f"omnireach author — {author.name or handle}" if author else f"omnireach author — {handle}"
        table = Table(title=f"{title}  ({len(envelope.results)}/{envelope.scanned} works, order={envelope.order})")
        table.add_column("#", style="dim")
        table.add_column("likes", justify="right", style="cyan")
        table.add_column("date", style="dim")
        table.add_column("title")
        table.add_column("URL", style="dim")
        for index, result in enumerate(envelope.results, start=1):
            likes = result.engagement.likes if result.engagement else None
            table.add_row(
                str(index),
                "-" if likes is None else f"{likes:,}",
                (result.ts or "")[:10],
                result.title[:60],
                result.url,
            )
        console.print(table)
        for warning in envelope.warnings:
            console.print(f"[yellow]warning: {warning}[/yellow]")
        for error in envelope.errors:
            console.print(f"[red]✗ {error.source}: {error.error}[/red]")

    if envelope.errors:
        raise click.exceptions.Exit(1)


__all__ = ["author_cmd"]
