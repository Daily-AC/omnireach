import json
from importlib.resources import files

from omnireach.native_bridge import NATIVE_EXTENSION_MIN_VERSION

EXTENSION_VERSION = "0.4.0"


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def test_packaged_extension_is_new_enough_for_the_bridge_gate():
    """The bridge refuses to hand a job to an extension below the minimum."""
    assert _version_tuple(EXTENSION_VERSION) >= _version_tuple(
        NATIVE_EXTENSION_MIN_VERSION
    )


def test_native_extension_manifest_has_narrow_permissions():
    manifest = json.loads(
        files("omnireach.chrome_extension")
        .joinpath("manifest.json")
        .read_text(encoding="utf-8")
    )

    assert manifest["manifest_version"] == 3
    assert manifest["version"] == EXTENSION_VERSION
    assert set(manifest["permissions"]) == {
        # alarms is the wake-up for the offscreen document that polls the
        # bridge; it grants no network or data access.
        "alarms",
        "offscreen",
        "scripting",
        "tabs",
    }
    assert set(manifest["host_permissions"]) == {
        "http://127.0.0.1:19826/*",
        "https://www.douyin.com/*",
        "https://www.google.com/*",
        "https://www.reddit.com/*",
        "https://www.tiktok.com/*",
        "https://www.xiaohongshu.com/*",
        "https://x.com/*",
    }
    serialized = json.dumps(manifest)
    assert "<all_urls>" not in serialized
    assert "cookies" not in manifest["permissions"]
    assert "debugger" not in manifest["permissions"]


def test_service_worker_contract_is_allowlisted_and_closes_background_tab():
    source = (
        files("omnireach.chrome_extension")
        .joinpath("service-worker.js")
        .read_text(encoding="utf-8")
    )

    assert '"system.ping"' in source
    assert '"douyin.author"' in source
    assert '"douyin.search"' in source
    assert '"google.search"' in source
    assert '"reddit.search"' in source
    assert '"tiktok.search"' in source
    assert 'data-e2e="search_top-item"' in source
    assert 'data-e2e="search-card-video-caption"' in source
    assert '"twitter.search"' in source
    assert '"xiaohongshu.search"' in source
    assert f'const EXTENSION_VERSION = "{EXTENSION_VERSION}"' in source
    assert "aweme/v1/web/aweme/post/" in source
    assert "if (!data.has_more)" in source
    assert "chrome.offscreen.closeDocument" not in source
    assert "injection.error" in source
    assert "commands: Array.from(COMMANDS).sort()" in source
    assert "active: false" in source
    assert "chrome.scripting.executeScript" in source
    assert "anchor.innerText" in source
    assert "finally" in source
    assert "chrome.tabs.remove" in source
    assert "chrome.windows.create" not in source
    assert "let offscreenInitialization" in source


def test_offscreen_bridge_contract_uses_authenticated_fixed_endpoints():
    source = (
        files("omnireach.chrome_extension")
        .joinpath("offscreen.js")
        .read_text(encoding="utf-8")
    )

    assert 'Authorization: `Bearer ${config.token}`' in source
    assert 'fetch(`${config.baseUrl}/v1/job?extension_version=${version}`' in source
    assert 'fetch(`${config.baseUrl}/v1/result`' in source
    assert 'method: "POST"' in source
    assert '"X-Omnireach-Extension-Version"' in source


def _service_worker_source() -> str:
    return (
        files("omnireach.chrome_extension")
        .joinpath("service-worker.js")
        .read_text(encoding="utf-8")
    )


def test_python_and_extension_agree_on_the_native_command_set():
    """A command allowed on one side and missing on the other fails silently.

    browser_transport routes on `_NATIVE_COMMANDS`; the extension gates on its
    own `COMMANDS` set. When they drift, `auto` mode either downgrades a
    supported command to OpenCLI or asks the extension for one it rejects.
    """
    import re

    from omnireach.browser_transport import _NATIVE_COMMANDS

    source = _service_worker_source()
    block = re.search(r"const COMMANDS = new Set\(\[(.*?)\]\)", source, re.S)
    assert block is not None, "service-worker.js no longer declares a COMMANDS set"
    declared = set(re.findall(r'"([a-z]+\.[a-z]+)"', block.group(1)))

    # system.* commands address the bridge itself, not a source, so they are
    # dispatched through run_native_job directly and listed here explicitly.
    expected = {f"{source_id}.{command}" for source_id, command in _NATIVE_COMMANDS}
    assert declared == expected | {"system.ping", "system.reload"}


def test_python_and_extension_agree_on_the_catalog_limit():
    from omnireach.author import MAX_AUTHOR_LIMIT

    limit = (
        files("omnireach.chrome_extension")
        .joinpath("douyin.js")
        .read_text(encoding="utf-8")
    )
    assert f"const MAX_AUTHOR_LIMIT = {MAX_AUTHOR_LIMIT};" in limit


def test_service_worker_answers_before_reloading_itself():
    """chrome.runtime.reload() destroys the document that delivers the reply."""
    source = _service_worker_source()

    assert '"system.reload"' in source
    reload_call = source.index("chrome.runtime.reload()")
    answer = source.index("reloading: true")
    assert reload_call < answer, "the reload must be deferred, not awaited"
    assert "setTimeout(() => chrome.runtime.reload(), RELOAD_DELAY_MS)" in source


def test_service_worker_keeps_the_offscreen_poller_alive_with_an_alarm():
    """Only the worker can recreate the offscreen document, and only an event
    wakes an idle worker — without the alarm a lost document is unrecoverable."""
    source = _service_worker_source()

    assert "chrome.alarms.create(KEEPALIVE_ALARM" in source
    assert "chrome.alarms.onAlarm.addListener" in source
    assert "periodInMinutes: 1" in source
