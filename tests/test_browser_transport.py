from unittest.mock import AsyncMock

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.browser_transport import run_browser_json
from omnireach.native_bridge import (
    NativeBridgeCommandError,
    NativeBridgeUnavailable,
)


async def test_auto_prefers_configured_native_bridge(monkeypatch):
    monkeypatch.delenv("OMNIREACH_BROWSER_TRANSPORT", raising=False)
    monkeypatch.setattr("omnireach.browser_transport.bridge_configured", lambda: True)
    monkeypatch.setattr(
        "omnireach.browser_transport.run_native_job",
        lambda command, payload, **kwargs: [{"desc": "native"}],
    )
    opencli = AsyncMock(side_effect=AssertionError("OpenCLI must not run"))
    monkeypatch.setattr("omnireach.browser_transport.run_opencli_json", opencli)

    result = await run_browser_json(
        "douyin",
        "search",
        {"query": "gpt5.6", "limit": 3},
        ("douyin", "search", "--limit", "3", "gpt5.6"),
    )

    assert result.adapter == "native-chrome"
    assert result.items == [{"desc": "native"}]
    opencli.assert_not_awaited()


async def test_auto_falls_back_only_when_native_bridge_is_unavailable(monkeypatch):
    monkeypatch.delenv("OMNIREACH_BROWSER_TRANSPORT", raising=False)
    monkeypatch.setattr("omnireach.browser_transport.bridge_configured", lambda: True)

    def unavailable(*args, **kwargs):
        raise NativeBridgeUnavailable("extension is not connected")

    monkeypatch.setattr("omnireach.browser_transport.run_native_job", unavailable)
    monkeypatch.setattr(
        "omnireach.browser_transport.run_opencli_json",
        AsyncMock(return_value=[{"desc": "fallback"}]),
    )

    result = await run_browser_json(
        "douyin", "search", {"query": "x"}, ("douyin", "search", "x")
    )

    assert result.adapter == "opencli"
    assert result.items == [{"desc": "fallback"}]


async def test_auto_does_not_hide_native_command_contract_failures(monkeypatch):
    monkeypatch.delenv("OMNIREACH_BROWSER_TRANSPORT", raising=False)
    monkeypatch.setattr("omnireach.browser_transport.bridge_configured", lambda: True)

    def broken(*args, **kwargs):
        raise NativeBridgeCommandError("selector contract changed")

    monkeypatch.setattr("omnireach.browser_transport.run_native_job", broken)
    opencli = AsyncMock(return_value=[])
    monkeypatch.setattr("omnireach.browser_transport.run_opencli_json", opencli)

    with pytest.raises(NativeBridgeCommandError, match="selector contract changed"):
        await run_browser_json(
            "douyin", "search", {"query": "x"}, ("douyin", "search", "x")
        )
    opencli.assert_not_awaited()


async def test_forced_native_reports_setup_error(monkeypatch):
    monkeypatch.setenv("OMNIREACH_BROWSER_TRANSPORT", "native")
    monkeypatch.setattr("omnireach.browser_transport.bridge_configured", lambda: False)

    with pytest.raises(AdapterUnavailable, match="bridge install"):
        await run_browser_json(
            "douyin", "search", {"query": "x"}, ("douyin", "search", "x")
        )


async def test_forced_opencli_skips_native_bridge(monkeypatch):
    monkeypatch.setenv("OMNIREACH_BROWSER_TRANSPORT", "opencli")
    monkeypatch.setattr(
        "omnireach.browser_transport.run_opencli_json",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "omnireach.browser_transport.run_native_job",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("native bridge must not run")
        ),
    )

    result = await run_browser_json(
        "douyin", "search", {"query": "x"}, ("douyin", "search", "x")
    )
    assert result.adapter == "opencli"


async def test_invalid_transport_mode_is_rejected(monkeypatch):
    monkeypatch.setenv("OMNIREACH_BROWSER_TRANSPORT", "magic")

    with pytest.raises(AdapterUnavailable, match="auto, native, opencli"):
        await run_browser_json(
            "douyin", "search", {"query": "x"}, ("douyin", "search", "x")
        )
