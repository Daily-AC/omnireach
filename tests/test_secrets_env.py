import os
from pathlib import Path

import pytest

from omnireach.secrets_env import load_secrets_env


def test_load_simple_kv(tmp_path: Path, monkeypatch):
    f = tmp_path / "secrets.env"
    f.write_text("FOO=bar\nBAZ=qux\n")
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    load_secrets_env(f)
    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "qux"


def test_load_strips_quotes(tmp_path: Path, monkeypatch):
    f = tmp_path / "secrets.env"
    f.write_text('FOO="bar baz"\nQUX=\'q\'\n')
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("QUX", raising=False)
    load_secrets_env(f)
    assert os.environ["FOO"] == "bar baz"
    assert os.environ["QUX"] == "q"


def test_load_ignores_comments_and_blank(tmp_path: Path, monkeypatch):
    f = tmp_path / "secrets.env"
    f.write_text("# comment\n\nFOO=bar\n")
    monkeypatch.delenv("FOO", raising=False)
    load_secrets_env(f)
    assert os.environ["FOO"] == "bar"


def test_load_does_not_override_existing_env(tmp_path: Path, monkeypatch):
    f = tmp_path / "secrets.env"
    f.write_text("FOO=fromfile\n")
    monkeypatch.setenv("FOO", "fromenv")
    load_secrets_env(f)
    assert os.environ["FOO"] == "fromenv"


def test_load_missing_file_is_noop(tmp_path: Path):
    load_secrets_env(tmp_path / "missing.env")  # no raise


def test_load_warns_on_loose_permissions(tmp_path: Path, capsys):
    f = tmp_path / "secrets.env"
    f.write_text("FOO=bar\n")
    f.chmod(0o644)
    load_secrets_env(f)
    captured = capsys.readouterr()
    assert "permission" in captured.err.lower() or "权限" in captured.err
