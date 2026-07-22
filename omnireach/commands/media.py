"""CLI commands for inspecting and parsing media URLs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from omnireach.media.service import inspect_media, parse_media

console = Console()


def _emit_json(explicit: bool) -> bool:
    forced = os.environ.get("OMNIREACH_FORCE_JSON", "").lower() in {"1", "true", "yes"}
    return explicit or forced or not sys.stdout.isatty()


def _render(envelope, json_out: bool) -> None:
    if _emit_json(json_out):
        click.echo(envelope.model_dump_json())
        return
    metadata = envelope.metadata
    table = Table(title=f"omnireach media — {envelope.source}")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("status", "ok" if envelope.ok else "failed")
    table.add_row("backend", envelope.backend or "-")
    table.add_row("type", envelope.media_type)
    table.add_row("title", metadata.title if metadata and metadata.title else "-")
    table.add_row("duration", f"{metadata.duration_ms / 1000:.1f}s" if metadata and metadata.duration_ms is not None else "-")
    table.add_row("subtitle tracks", str(len(envelope.tracks)))
    table.add_row("artifacts", str(len(envelope.artifacts)))
    console.print(table)
    for warning in envelope.warnings:
        console.print(f"[yellow]warning: {warning}[/yellow]")
    for error in envelope.errors:
        console.print(f"[red]{error.stage}: {error.message}[/red]")
        if error.hint:
            console.print(f"[dim]{error.hint}[/dim]")


def _backend_option(function):
    return click.option(
        "--backend",
        type=click.Choice(["auto", "direct", "yt-dlp", "bilibili-api"]),
        default="auto",
        show_default=True,
    )(function)


@click.group("media")
def media_cmd() -> None:
    """Inspect media metadata and materialize transcript artifacts."""


@media_cmd.command("inspect")
@click.argument("url")
@_backend_option
@click.option("--timeout", type=click.FloatRange(min=1, max=300), default=60, show_default=True)
@click.option(
    "--cookies-from-browser",
    help="Explicitly reuse yt-dlp browser cookies, e.g. chrome:Profile 1",
)
@click.option("--json", "json_out", is_flag=True, help="Output a JSON envelope")
def media_inspect_cmd(
    url: str,
    backend: str,
    timeout: float,
    cookies_from_browser: str | None,
    json_out: bool,
) -> None:
    """Inspect metadata and available subtitle tracks without writing files."""
    envelope = inspect_media(
        url,
        backend=backend,
        cookies_from_browser=cookies_from_browser,
        timeout=timeout,
    )
    _render(envelope, json_out)
    if not envelope.ok:
        raise click.exceptions.Exit(1)


@media_cmd.command("parse")
@click.argument("url")
@click.option("--mode", type=click.Choice(["quick"]), default="quick", show_default=True)
@_backend_option
@click.option("--language", help="Preferred subtitle language, e.g. en or zh-Hans")
@click.option("--subtitle-url", help="HTTP(S) sidecar VTT, SRT, or JSON3 subtitle")
@click.option(
    "--cookies-from-browser",
    help="Explicitly reuse yt-dlp browser cookies, e.g. chrome:Profile 1",
)
@click.option("--output-dir", type=click.Path(path_type=Path, file_okay=False))
@click.option("--cache/--no-cache", "reuse_cache", default=True, show_default=True)
@click.option(
    "--max-duration",
    type=click.FloatRange(min=1, max=86400),
    help="Reject media longer than this many seconds",
)
@click.option("--timeout", type=click.FloatRange(min=1, max=300), default=60, show_default=True)
@click.option("--json", "json_out", is_flag=True, help="Output a JSON envelope")
def media_parse_cmd(
    url: str,
    mode: str,
    backend: str,
    language: str | None,
    subtitle_url: str | None,
    cookies_from_browser: str | None,
    output_dir: Path | None,
    reuse_cache: bool,
    max_duration: float | None,
    timeout: float,
    json_out: bool,
) -> None:
    """Write normalized metadata and transcript artifacts for a media URL."""
    envelope = parse_media(
        url,
        mode=mode,
        backend=backend,
        language=language,
        subtitle_url=subtitle_url,
        cookies_from_browser=cookies_from_browser,
        output_dir=output_dir,
        reuse_cache=reuse_cache,
        max_duration=max_duration,
        timeout=timeout,
    )
    _render(envelope, json_out)
    if not envelope.ok:
        raise click.exceptions.Exit(1)


__all__ = ["media_cmd"]
