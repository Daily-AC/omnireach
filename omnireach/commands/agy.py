"""Configure the dedicated agy conversation used for grounded search."""

from __future__ import annotations

import asyncio
import json

import click

from omnireach.adapters.agy import (
    AgyGroundedAdapter,
    _agentapi_address,
    clear_configured_conversation,
    configure_conversation,
    configured_conversation_id,
)


def _emit(payload: dict[str, object], json_out: bool) -> None:
    if json_out:
        click.echo(json.dumps(payload, ensure_ascii=False))
        return
    for key, value in payload.items():
        click.echo(f"{key}: {value}")


@click.group("agy")
def agy_cmd() -> None:
    """Manage the experimental agy grounded-search backend."""


@agy_cmd.command("configure")
@click.argument("conversation_id")
@click.option("--json", "json_out", is_flag=True, help="Output JSON")
def configure_cmd(conversation_id: str, json_out: bool) -> None:
    try:
        path = configure_conversation(conversation_id)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    _emit(
        {
            "configured": True,
            "conversation_id": conversation_id,
            "config": str(path),
        },
        json_out,
    )


@agy_cmd.command("status")
@click.option("--json", "json_out", is_flag=True, help="Output JSON")
def status_cmd(json_out: bool) -> None:
    conversation_id = configured_conversation_id()
    ready = asyncio.run(AgyGroundedAdapter().is_ready())
    _emit(
        {
            "configured": conversation_id is not None,
            "conversation_id": conversation_id,
            "agentapi_address": _agentapi_address(),
            "ready": ready,
        },
        json_out,
    )


@agy_cmd.command("clear")
@click.option("--json", "json_out", is_flag=True, help="Output JSON")
def clear_cmd(json_out: bool) -> None:
    path = clear_configured_conversation()
    _emit({"configured": False, "config": str(path)}, json_out)
