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
