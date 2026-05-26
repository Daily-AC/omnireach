from pathlib import Path

from click.testing import CliRunner

from omnireach.cli import main


def test_init_writes_default_preferences(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    p = tmp_path / ".omnireach" / "preferences.toml"
    assert p.exists()
    assert "[defaults]" in p.read_text()


def test_init_does_not_install_agent_reach(monkeypatch, tmp_path):
    """v0.6.1: init no longer auto-installs agent-reach."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def boom(*args, **kwargs):
        raise AssertionError(f"installer should not be called from init: {args} {kwargs}")

    monkeypatch.setattr("omnireach.installer.install_pipx_package", boom)
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0


def test_init_prints_next_step_hints(monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    out = result.output
    assert "omnireach sources" in out
    assert "omnireach setup" in out
    assert "hackernews" in out


def test_init_idempotent_when_prefs_exist(monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    pref_path = tmp_path / ".omnireach" / "preferences.toml"
    pref_path.parent.mkdir(parents=True, exist_ok=True)
    pref_path.write_text("[defaults]\nlang = 'en-US'\n")

    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    # File preserved, not overwritten
    assert "en-US" in pref_path.read_text()
    assert "已存在" in result.output or "exists" in result.output.lower()


def test_init_accepts_legacy_yes_flag(monkeypatch, tmp_path):
    """--yes is now a deprecated no-op; still accepted for back-compat."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init", "--yes"])
    assert result.exit_code == 0
