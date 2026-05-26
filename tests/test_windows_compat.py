"""Tests for v0.6.3 Windows hardening.

These tests run on any platform; they assert that the code paths gated by
`os.name == 'nt'` behave correctly when simulated.
"""

import os
from pathlib import Path

import pytest


def test_secrets_env_skips_permission_check_on_windows(tmp_path: Path, monkeypatch, capsys):
    """On Windows (os.name == 'nt') the POSIX permission warning must NOT fire,
    even when the file would look 'loose' under POSIX semantics."""
    monkeypatch.setattr("os.name", "nt")
    from omnireach.secrets_env import load_secrets_env

    secrets = tmp_path / "secrets.env"
    secrets.write_text("FOO=bar\n")
    # On POSIX we'd chmod 0o644 to trigger the warning; on Windows-mocked it should NOT warn
    secrets.chmod(0o644)

    monkeypatch.delenv("FOO", raising=False)
    load_secrets_env(secrets)
    captured = capsys.readouterr()
    assert "permission" not in captured.err.lower()
    assert "权限" not in captured.err
    assert os.environ.get("FOO") == "bar"


def test_secrets_env_still_warns_on_posix(tmp_path: Path, monkeypatch, capsys):
    """POSIX behavior unchanged: loose perms still print a warning."""
    if os.name == "nt":
        pytest.skip("Test only meaningful on POSIX")
    from omnireach.secrets_env import load_secrets_env

    secrets = tmp_path / "secrets.env"
    secrets.write_text("FOO=bar\n")
    secrets.chmod(0o644)
    monkeypatch.delenv("FOO", raising=False)
    load_secrets_env(secrets)
    captured = capsys.readouterr()
    assert "permission" in captured.err.lower() or "权限" in captured.err


def test_default_editor_picks_notepad_on_windows(monkeypatch):
    monkeypatch.setattr("os.name", "nt")
    monkeypatch.delenv("EDITOR", raising=False)
    # Pretend nothing is on PATH so the function falls through to the bare 'notepad' default
    monkeypatch.setattr("shutil.which", lambda b: None)
    from omnireach.commands.preferences import _default_editor

    assert _default_editor() == "notepad"


def test_default_editor_prefers_env_editor(monkeypatch):
    monkeypatch.setenv("EDITOR", "code --wait")
    from omnireach.commands.preferences import _default_editor

    assert _default_editor() == "code --wait"


def test_default_editor_posix_fallback(monkeypatch):
    monkeypatch.setattr("os.name", "posix")
    monkeypatch.delenv("EDITOR", raising=False)
    # Make only 'vi' exist on PATH
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/vi" if b == "vi" else None)
    from omnireach.commands.preferences import _default_editor

    assert _default_editor() == "vi"


def test_setup_github_hint_mentions_winget():
    """github setup manual_hint must include the Windows install path now."""
    from omnireach.commands.setup import BINARY_GUIDES

    hint = BINARY_GUIDES["github"]["manual_hint"]
    assert "winget" in hint
    assert "brew" in hint  # mac still there


def test_setup_booster_skips_chmod_on_windows(tmp_path: Path, monkeypatch):
    """On Windows, _setup_booster must not call Path.chmod (POSIX permissions don't apply)."""
    monkeypatch.setattr("os.name", "nt")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    chmod_called = {"hit": False}
    orig_chmod = Path.chmod

    def spy_chmod(self, *args, **kwargs):
        chmod_called["hit"] = True
        return orig_chmod(self, *args, **kwargs)

    monkeypatch.setattr(Path, "chmod", spy_chmod)

    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "tavily"], input="y\ntvly-test\n")
    assert result.exit_code == 0
    assert chmod_called["hit"] is False


def test_doctor_prints_platform_info(monkeypatch):
    """doctor command prints a platform/python info line at the top — useful for issue reports."""
    monkeypatch.setattr("shutil.which", lambda b: None)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    out = result.output
    assert "omnireach" in out
    assert "Python" in out
