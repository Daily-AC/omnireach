import json
from importlib.resources import files


def test_native_extension_manifest_has_narrow_permissions():
    manifest = json.loads(
        files("omnireach.chrome_extension")
        .joinpath("manifest.json")
        .read_text(encoding="utf-8")
    )

    assert manifest["manifest_version"] == 3
    assert set(manifest["permissions"]) == {
        "offscreen",
        "scripting",
        "tabs",
        "windows",
    }
    assert set(manifest["host_permissions"]) == {
        "http://127.0.0.1:19826/*",
        "https://www.douyin.com/*",
    }
    serialized = json.dumps(manifest)
    assert "<all_urls>" not in serialized
    assert "cookies" not in manifest["permissions"]
    assert "debugger" not in manifest["permissions"]


def test_service_worker_contract_is_allowlisted_and_closes_hidden_window():
    source = (
        files("omnireach.chrome_extension")
        .joinpath("service-worker.js")
        .read_text(encoding="utf-8")
    )

    assert '"system.ping"' in source
    assert '"douyin.search"' in source
    assert 'extensionVersion: "0.1.0"' in source
    assert "focused: false" in source
    assert "chrome.scripting.executeScript" in source
    assert "finally" in source
    assert "chrome.windows.remove" in source


def test_offscreen_bridge_contract_uses_authenticated_fixed_endpoints():
    source = (
        files("omnireach.chrome_extension")
        .joinpath("offscreen.js")
        .read_text(encoding="utf-8")
    )

    assert 'Authorization: `Bearer ${config.token}`' in source
    assert 'fetch(`${config.baseUrl}/v1/job`' in source
    assert 'fetch(`${config.baseUrl}/v1/result`' in source
    assert 'method: "POST"' in source
