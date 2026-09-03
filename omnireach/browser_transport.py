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
from omnireach.native_bridge import (
    NativeBridgeCommandError,
    NativeBridgeUnavailable,
    run_native_job,
)

_VALID_MODES = {"auto", "native", "opencli"}
_NATIVE_COMMANDS = {
    ("douyin", "author"),
    ("douyin", "search"),
    ("google", "search"),
    ("reddit", "search"),
    ("tiktok", "search"),
    ("twitter", "search"),
    ("xiaohongshu", "search"),
}


@dataclass(frozen=True)
class BrowserCommandResult:
    items: list[dict[str, Any]]
    adapter: str


async def _run_native(
    command: str,
    payload: dict[str, object],
    result_timeout: float | None = None,
) -> list[dict[str, Any]]:
    cancel_event = threading.Event()
    kwargs: dict[str, Any] = {"cancel_event": cancel_event}
    if result_timeout is not None:
        kwargs["result_timeout"] = result_timeout
    worker = asyncio.create_task(
        asyncio.to_thread(
            run_native_job,
            command,
            payload,
            **kwargs,
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


_STALE_EXTENSION_HINT = (
    "run `omnireach bridge install && omnireach bridge reload`; if that extension "
    "predates `system.reload`, reload it once at chrome://extensions instead "
    "(`omnireach bridge status` reports reload_required)"
)


async def run_browser_json(
    source: str,
    command: str,
    payload: dict[str, object],
    opencli_args: tuple[str, ...] | None = None,
    *,
    result_timeout: float | None = None,
) -> BrowserCommandResult:
    """Run one browser-backed command.

    `opencli_args=None` marks a command the OpenCLI fallback cannot serve, so
    the native bridge becomes the only path and its failures surface as
    actionable `AdapterUnavailable` errors instead of a silent downgrade.
    """
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
    native_only = opencli_args is None
    if native_only and not native_supported:
        raise AdapterUnavailable(
            source, f"native Chrome transport does not support {source}.{command}"
        )
    if mode == "opencli" and native_only:
        raise AdapterUnavailable(
            source,
            f"{source}.{command} requires the native Chrome bridge; "
            "OpenCLI has no equivalent command",
            hint=_STALE_EXTENSION_HINT,
        )

    try_native = (
        mode == "native"
        or native_only
        or (mode == "auto" and native_supported and bridge_configured())
    )
    if try_native:
        if not bridge_configured():
            raise AdapterUnavailable(
                source,
                "native Chrome bridge is not installed; run `omnireach bridge install`",
                hint="omnireach bridge install",
            )
        try:
            items = await _run_native(
                f"{source}.{command}", payload, result_timeout,
            )
            return BrowserCommandResult(items=items, adapter="native-chrome")
        except NativeBridgeCommandError as exc:
            if "command is not allowed" not in str(exc) or mode == "native":
                raise
            if native_only:
                raise AdapterUnavailable(
                    source,
                    f"the connected Chrome extension does not implement "
                    f"{source}.{command}",
                    hint=_STALE_EXTENSION_HINT,
                ) from exc
            # Extension 0.1.x only allowed douyin.search. In auto mode an old
            # unpacked extension should remain a compatibility fallback case,
            # not turn every newly migrated adapter into a hard failure.
        except NativeBridgeUnavailable as exc:
            if mode == "native" or native_only:
                raise AdapterUnavailable(
                    source,
                    str(exc),
                    hint="omnireach bridge install",
                ) from exc

    items = await run_opencli_json(source, *opencli_args)
    return BrowserCommandResult(items=items, adapter="opencli")
