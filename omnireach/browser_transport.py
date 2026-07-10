"""Select the native Chrome bridge or OpenCLI for browser-backed adapters."""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass
from typing import Any

from omnireach.adapters._opencli import run_opencli_json
from omnireach.adapters.base import AdapterUnavailable
from omnireach.bridge_install import bridge_configured
from omnireach.native_bridge import NativeBridgeUnavailable, run_native_job

_VALID_MODES = {"auto", "native", "opencli"}
_NATIVE_COMMANDS = {("douyin", "search")}


@dataclass(frozen=True)
class BrowserCommandResult:
    items: list[dict[str, Any]]
    adapter: str


async def _run_native(
    command: str,
    payload: dict[str, object],
) -> list[dict[str, Any]]:
    cancel_event = threading.Event()
    worker = asyncio.create_task(
        asyncio.to_thread(
            run_native_job,
            command,
            payload,
            cancel_event=cancel_event,
        )
    )
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        cancel_event.set()
        try:
            await worker
        except NativeBridgeUnavailable:
            pass
        raise


async def run_browser_json(
    source: str,
    command: str,
    payload: dict[str, object],
    opencli_args: tuple[str, ...],
) -> BrowserCommandResult:
    mode = os.environ.get("OMNIREACH_BROWSER_TRANSPORT", "auto").strip().lower()
    if mode not in _VALID_MODES:
        raise AdapterUnavailable(
            source,
            "OMNIREACH_BROWSER_TRANSPORT must be one of: auto, native, opencli",
        )

    native_supported = (source, command) in _NATIVE_COMMANDS
    if mode == "native" and not native_supported:
        raise AdapterUnavailable(
            source, f"native Chrome transport does not support {source}.{command}"
        )

    try_native = mode == "native" or (
        mode == "auto" and native_supported and bridge_configured()
    )
    if try_native:
        if not bridge_configured():
            raise AdapterUnavailable(
                source,
                "native Chrome bridge is not installed; run `omnireach bridge install`",
                hint="omnireach bridge install",
            )
        try:
            items = await _run_native(f"{source}.{command}", payload)
            return BrowserCommandResult(items=items, adapter="native-chrome")
        except NativeBridgeUnavailable as exc:
            if mode == "native":
                raise AdapterUnavailable(
                    source,
                    str(exc),
                    hint="omnireach bridge install",
                ) from exc

    items = await run_opencli_json(source, *opencli_args)
    return BrowserCommandResult(items=items, adapter="opencli")
