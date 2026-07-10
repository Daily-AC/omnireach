"""Shared, cancellation-safe OpenCLI bridge for browser-backed adapters."""

from __future__ import annotations

import asyncio
import json
import shutil
from typing import Any

from omnireach.adapters.base import AdapterUnavailable


SILENT_BROWSER_ARGS = (
    "--window", "background",
    "--site-session", "ephemeral",
    "--keep-tab", "false",
)


async def _stop_process(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()


async def run_opencli_json(source: str, *args: str) -> list[dict[str, Any]]:
    """Run an OpenCLI adapter in a hidden, short-lived browser tab."""
    if not shutil.which("opencli"):
        raise AdapterUnavailable(
            source, "opencli not installed", hint=f"omnireach setup {source}"
        )
    proc = await asyncio.create_subprocess_exec(
        "opencli", *args, "--format", "json", *SILENT_BROWSER_ARGS,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await proc.communicate()
    except asyncio.CancelledError:
        await _stop_process(proc)
        raise
    if proc.returncode != 0:
        detail = err.decode().strip() or out.decode().strip()
        raise AdapterUnavailable(
            source, detail or f"opencli {source} command failed"
        )
    try:
        data = json.loads(out.decode())
    except json.JSONDecodeError as e:
        raise AdapterUnavailable(source, f"opencli returned non-JSON: {e}") from e
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("results", [])
    else:
        raise AdapterUnavailable(source, "opencli returned an invalid result shape")
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise AdapterUnavailable(source, "opencli returned an invalid result shape")
    return items
