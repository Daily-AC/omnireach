from pathlib import Path

import pytest

from omnireach.preferences import (
    Preferences,
    load_preferences,
    write_default_preferences,
    DEFAULT_PREFERENCES_TOML,
)


def test_default_preferences_values():
    p = Preferences()
    assert "web" in p.defaults.on
    assert p.defaults.lang == "zh-CN"
    assert p.output.format == "tty"
    assert p.output.max_results_per_source == 8
    assert p.boosters.auto_enable is True
    assert p.trust_overrides == {}


def test_load_preferences_missing_returns_default(tmp_path: Path):
    p = load_preferences(tmp_path / "nonexistent.toml")
    assert isinstance(p, Preferences)
    assert p.defaults.lang == "zh-CN"


def test_load_preferences_valid(tmp_path: Path):
    f = tmp_path / "preferences.toml"
    f.write_text(
        """
[defaults]
on = ["hackernews"]
lang = "en-US"

[output]
max_results_per_source = 20

[boosters]
auto_enable = false

[trust_overrides]
web = 0.95
"""
    )
    p = load_preferences(f)
    assert p.defaults.on == ["hackernews"]
    assert p.defaults.lang == "en-US"
    assert p.output.max_results_per_source == 20
    assert p.boosters.auto_enable is False
    assert p.trust_overrides == {"web": 0.95}


def test_load_preferences_invalid_falls_back_with_warning(tmp_path: Path, capsys):
    f = tmp_path / "preferences.toml"
    f.write_text("this is { not valid toml ===")
    p = load_preferences(f)
    assert isinstance(p, Preferences)
    err = capsys.readouterr().err
    assert "preferences" in err.lower()


def test_write_default_preferences_roundtrip(tmp_path: Path):
    f = tmp_path / "preferences.toml"
    write_default_preferences(f)
    assert f.exists()
    assert "[defaults]" in f.read_text()
    p = load_preferences(f)
    assert p.defaults.lang == "zh-CN"


def test_default_toml_has_comments():
    assert "#" in DEFAULT_PREFERENCES_TOML
