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


@pytest.mark.parametrize(
    "source",
    ["google", "reddit", "tiktok", "twitter", "xiaohongshu"],
)
async def test_remaining_browser_sources_support_native_transport(monkeypatch, source):
    monkeypatch.setenv("OMNIREACH_BROWSER_TRANSPORT", "native")
    monkeypatch.setattr("omnireach.browser_transport.bridge_configured", lambda: True)
    monkeypatch.setattr(
        "omnireach.browser_transport.run_native_job",
        lambda command, payload, **kwargs: [{"command": command}],
    )

    result = await run_browser_json(
        source,
        "search",
        {"query": "test", "limit": 1},
        (source, "search", "test"),
    )

    assert result.adapter == "native-chrome"
    assert result.items == [{"command": f"{source}.search"}]


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


async def test_auto_falls_back_from_pre_02_extension_command_allowlist(monkeypatch):
    monkeypatch.delenv("OMNIREACH_BROWSER_TRANSPORT", raising=False)
    monkeypatch.setattr("omnireach.browser_transport.bridge_configured", lambda: True)

    def old_extension(*args, **kwargs):
        raise NativeBridgeCommandError("command is not allowed")

    monkeypatch.setattr("omnireach.browser_transport.run_native_job", old_extension)
    monkeypatch.setattr(
        "omnireach.browser_transport.run_opencli_json",
        AsyncMock(return_value=[{"title": "fallback"}]),
    )

    result = await run_browser_json(
        "google", "search", {"query": "x"}, ("google", "search", "x")
    )

    assert result.adapter == "opencli"
    assert result.items == [{"title": "fallback"}]


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


async def test_native_only_command_never_downgrades_to_opencli(monkeypatch):
    """douyin.author has no OpenCLI equivalent, so a downgrade would lie."""
    monkeypatch.delenv("OMNIREACH_BROWSER_TRANSPORT", raising=False)
    monkeypatch.setattr("omnireach.browser_transport.bridge_configured", lambda: True)
    monkeypatch.setattr(
        "omnireach.browser_transport.run_native_job",
        lambda command, payload, **kwargs: [{"command": command, **kwargs}],
    )
    opencli = AsyncMock(side_effect=AssertionError("OpenCLI must not run"))
    monkeypatch.setattr("omnireach.browser_transport.run_opencli_json", opencli)

    result = await run_browser_json(
        "douyin", "author", {"handle": "x"}, result_timeout=120,
    )

    assert result.adapter == "native-chrome"
    assert result.items[0]["command"] == "douyin.author"
    assert result.items[0]["result_timeout"] == 120
    opencli.assert_not_awaited()


async def test_stale_extension_asks_for_a_reload_instead_of_falling_back(monkeypatch):
    monkeypatch.delenv("OMNIREACH_BROWSER_TRANSPORT", raising=False)
    monkeypatch.setattr("omnireach.browser_transport.bridge_configured", lambda: True)

    def stale(command, payload, **kwargs):
        raise NativeBridgeCommandError(
            'command is not allowed: "douyin.author"; allowed=["douyin.search"]'
        )

    monkeypatch.setattr("omnireach.browser_transport.run_native_job", stale)
    opencli = AsyncMock(side_effect=AssertionError("OpenCLI must not run"))
    monkeypatch.setattr("omnireach.browser_transport.run_opencli_json", opencli)

    with pytest.raises(AdapterUnavailable) as exc_info:
        await run_browser_json("douyin", "author", {"handle": "x"})

    assert "does not implement douyin.author" in exc_info.value.reason
    assert "reload the unpacked extension" in exc_info.value.hint
    opencli.assert_not_awaited()


async def test_native_only_command_reports_a_missing_bridge(monkeypatch):
    monkeypatch.delenv("OMNIREACH_BROWSER_TRANSPORT", raising=False)
    monkeypatch.setattr("omnireach.browser_transport.bridge_configured", lambda: False)
    opencli = AsyncMock(side_effect=AssertionError("OpenCLI must not run"))
    monkeypatch.setattr("omnireach.browser_transport.run_opencli_json", opencli)

    with pytest.raises(AdapterUnavailable) as exc_info:
        await run_browser_json("douyin", "author", {"handle": "x"})

    assert "bridge install" in exc_info.value.hint
    opencli.assert_not_awaited()


async def test_opencli_mode_cannot_serve_a_native_only_command(monkeypatch):
    monkeypatch.setenv("OMNIREACH_BROWSER_TRANSPORT", "opencli")

    with pytest.raises(AdapterUnavailable) as exc_info:
        await run_browser_json("douyin", "author", {"handle": "x"})

    assert "requires the native Chrome bridge" in exc_info.value.reason


async def test_native_only_bridge_disconnect_is_actionable(monkeypatch):
    monkeypatch.delenv("OMNIREACH_BROWSER_TRANSPORT", raising=False)
    monkeypatch.setattr("omnireach.browser_transport.bridge_configured", lambda: True)

    def disconnected(command, payload, **kwargs):
        raise NativeBridgeUnavailable("native bridge extension did not connect")

    monkeypatch.setattr("omnireach.browser_transport.run_native_job", disconnected)
    opencli = AsyncMock(side_effect=AssertionError("OpenCLI must not run"))
    monkeypatch.setattr("omnireach.browser_transport.run_opencli_json", opencli)

    with pytest.raises(AdapterUnavailable) as exc_info:
        await run_browser_json("douyin", "author", {"handle": "x"})

    assert "did not connect" in exc_info.value.reason
    opencli.assert_not_awaited()
