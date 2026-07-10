import json
import tomllib
from pathlib import Path

from omnireach import __version__


ROOT = Path(__file__).parents[1]


def test_package_runtime_and_plugin_versions_match():
    pyproject = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    plugin = json.loads(
        (ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    )

    assert pyproject["project"]["version"] == __version__
    assert plugin["version"] == __version__


def test_packaged_readme_does_not_link_to_unshipped_relative_assets():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "](./" not in readme
    assert "](LICENSE)" not in readme
