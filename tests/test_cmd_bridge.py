import json

from click.testing import CliRunner

from omnireach.cli import main


def test_bridge_install_json_reports_stable_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))

    result = CliRunner().invoke(main, ["bridge", "install", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["installed"] is True
    assert payload["extension_dir"] == str(
        tmp_path / ".omnireach" / "chrome-extension"
    )
    assert payload["load_unpacked"] == payload["extension_dir"]


def test_bridge_path_json_does_not_install(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))

    result = CliRunner().invoke(main, ["bridge", "path", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["configured"] is False
    assert not (tmp_path / ".omnireach" / "bridge-token").exists()


def test_bridge_status_json_reports_real_ping(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    CliRunner().invoke(main, ["bridge", "install", "--json"])
    monkeypatch.setattr(
        "omnireach.commands.bridge.probe_native_bridge",
        lambda: {"pong": True, "extensionVersion": "0.1.0"},
    )

    result = CliRunner().invoke(main, ["bridge", "status", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["installed"] is True
    assert payload["connected"] is True
    assert payload["extension_version"] == "0.1.0"


def test_bridge_status_json_reports_connection_error(monkeypatch, tmp_path):
    from omnireach.native_bridge import NativeBridgeUnavailable

    monkeypatch.setenv("HOME", str(tmp_path))
    CliRunner().invoke(main, ["bridge", "install", "--json"])

    def unavailable():
        raise NativeBridgeUnavailable("extension did not connect")

    monkeypatch.setattr(
        "omnireach.commands.bridge.probe_native_bridge", unavailable
    )

    result = CliRunner().invoke(main, ["bridge", "status", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["installed"] is True
    assert payload["connected"] is False
    assert payload["error"] == "extension did not connect"
