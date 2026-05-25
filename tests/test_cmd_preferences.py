from pathlib import Path

import pytest
from click.testing import CliRunner

from omnireach.cli import main


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def test_preferences_path_prints_expected_path(tmp_home):
    runner = CliRunner()
    result = runner.invoke(main, ["preferences", "path"])
    assert result.exit_code == 0
    assert str(tmp_home / ".omnireach" / "preferences.toml") in result.output


def test_preferences_show_prints_defaults_when_no_file(tmp_home):
    runner = CliRunner()
    result = runner.invoke(main, ["preferences", "show"])
    assert result.exit_code == 0
    assert "zh-CN" in result.output


def test_preferences_reset_creates_file(tmp_home):
    runner = CliRunner()
    result = runner.invoke(main, ["preferences", "reset"])
    assert result.exit_code == 0
    p = tmp_home / ".omnireach" / "preferences.toml"
    assert p.exists()
    assert "[defaults]" in p.read_text()


def test_preferences_reset_backs_up_existing(tmp_home):
    p = tmp_home / ".omnireach" / "preferences.toml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# my edits\n[defaults]\nlang = 'en-US'\n")
    runner = CliRunner()
    result = runner.invoke(main, ["preferences", "reset"])
    assert result.exit_code == 0
    backup = p.with_suffix(".toml.bak")
    assert backup.exists()
    assert "en-US" in backup.read_text()
