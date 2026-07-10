import json
import stat

from omnireach.bridge_install import bridge_paths, install_extension


def test_install_extension_is_idempotent_and_preserves_token(tmp_path):
    first = install_extension(home=tmp_path)
    first_token = first.token_path.read_text().strip()

    second = install_extension(home=tmp_path)

    assert second == first
    assert second.token_path.read_text().strip() == first_token
    assert len(first_token) >= 32
    assert stat.S_IMODE(first.token_path.stat().st_mode) == 0o600


def test_install_extension_copies_assets_and_generates_config(tmp_path):
    paths = install_extension(home=tmp_path)

    manifest = json.loads((paths.extension_dir / "manifest.json").read_text())
    config = (paths.extension_dir / "bridge-config.js").read_text()

    assert manifest["name"] == "Omnireach Native Bridge"
    assert (paths.extension_dir / "offscreen.html").exists()
    assert paths.token_path.read_text().strip() in config
    assert "bridge-config.example.js" not in {
        item.name for item in paths.extension_dir.iterdir()
    }


def test_bridge_paths_use_stable_user_directory(tmp_path):
    paths = bridge_paths(home=tmp_path)

    assert paths.root == tmp_path / ".omnireach"
    assert paths.extension_dir == tmp_path / ".omnireach" / "chrome-extension"
    assert paths.token_path == tmp_path / ".omnireach" / "bridge-token"
