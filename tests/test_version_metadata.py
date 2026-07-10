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
