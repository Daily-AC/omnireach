"""Tests for `omnireach fetch <url>` subcommand (v0.10)."""

import json as _json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from omnireach.cli import main
from omnireach.commands.fetch import (
    _fetch_via_crwl,
    _fetch_via_jina,
    _should_emit_json,
)


def test_fetch_help_lists_backend_options():
    runner = CliRunner()
    res = runner.invoke(main, ["fetch", "--help"])
    assert res.exit_code == 0
    assert "crwl" in res.output
    assert "jina" in res.output
    assert "--backend" in res.output


def test_fetch_via_crwl_returns_subprocess_stdout(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/local/bin/{b}" if b == "crwl" else None)
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = "# article title\n\nbody content here"
    proc.stderr = ""
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: proc)
    out = _fetch_via_crwl("https://example.com", timeout=10.0)
    assert "article title" in out


def test_fetch_via_crwl_missing_binary_raises(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    with pytest.raises(RuntimeError) as exc:
        _fetch_via_crwl("https://example.com", timeout=10.0)
    assert "crwl 不在 PATH" in str(exc.value)


def test_fetch_via_crwl_nonzero_exit_raises(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/local/bin/{b}")
    proc = MagicMock()
    proc.returncode = 1
    proc.stdout = ""
    proc.stderr = "boom"
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: proc)
    with pytest.raises(RuntimeError) as exc:
        _fetch_via_crwl("https://example.com", timeout=10.0)
    assert "crwl 失败" in str(exc.value)


def test_fetch_via_jina_returns_response_text(monkeypatch):
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = "# jina markdown\n\nhello"

    class FakeClient:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url, headers=None): return fake_resp

    monkeypatch.setattr("omnireach.commands.fetch.httpx.Client", FakeClient)
    out = _fetch_via_jina("https://example.com", timeout=10.0)
    assert "jina markdown" in out


def test_fetch_via_jina_4xx_raises(monkeypatch):
    fake_resp = MagicMock()
    fake_resp.status_code = 404
    fake_resp.text = ""

    class FakeClient:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url, headers=None): return fake_resp

    monkeypatch.setattr("omnireach.commands.fetch.httpx.Client", FakeClient)
    with pytest.raises(RuntimeError) as exc:
        _fetch_via_jina("https://example.com", timeout=10.0)
    assert "404" in str(exc.value)


def test_fetch_auto_falls_back_to_jina_when_crwl_missing(monkeypatch):
    """auto backend: crwl raises (not installed) → jina succeeds → use jina."""
    def fake_crwl(*a, **kw):
        raise RuntimeError("crwl 不在 PATH")
    def fake_jina(url, timeout):
        return "# from jina\nfallback worked"
    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_crwl", fake_crwl)
    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_jina", fake_jina)
    runner = CliRunner()
    res = runner.invoke(main, ["fetch", "https://example.com", "--json"])
    assert res.exit_code == 0
    json_line = next((l for l in res.output.splitlines() if l.strip().startswith("{")), None)
    assert json_line is not None
    data = _json.loads(json_line)
    assert data["backend"] == "jina"
    assert "fallback worked" in data["content_markdown"]


def test_fetch_explicit_crwl_backend_no_fallback(monkeypatch):
    """--backend crwl only tries crwl; if it fails, no jina fallback."""
    def fake_crwl(*a, **kw):
        raise RuntimeError("crwl 不在 PATH")
    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_crwl", fake_crwl)
    runner = CliRunner()
    res = runner.invoke(main, ["fetch", "https://example.com", "--backend", "crwl", "--json"])
    json_line = next((l for l in res.output.splitlines() if l.strip().startswith("{")), None)
    assert json_line is not None
    data = _json.loads(json_line)
    assert data["backend"] is None
    assert data["content_markdown"] == ""
    assert any("crwl" in e for e in data["errors"])


def test_fetch_returns_envelope_with_url_and_backend(monkeypatch):
    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_crwl",
                        lambda url, timeout: "# hello")
    runner = CliRunner()
    res = runner.invoke(main, ["fetch", "https://example.com", "--json"])
    json_line = next((l for l in res.output.splitlines() if l.strip().startswith("{")), None)
    data = _json.loads(json_line)
    assert data["url"] == "https://example.com"
    assert data["backend"] == "crwl"
    assert data["content_markdown"] == "# hello"
    assert data["fetched_at"].endswith("Z")
    assert data["errors"] == []


def test_should_emit_json_explicit_flag_wins():
    assert _should_emit_json(True) is True


def test_should_emit_json_force_env_var(monkeypatch):
    """v0.10: OMNIREACH_FORCE_JSON=1 forces JSON regardless of TTY state."""
    monkeypatch.setenv("OMNIREACH_FORCE_JSON", "1")
    # Even with explicit_flag=False and (hypothetically) isatty=True, should be True
    assert _should_emit_json(False) is True


def test_should_emit_json_force_env_var_accepts_true_yes(monkeypatch):
    for val in ("true", "yes", "TRUE", "YES"):
        monkeypatch.setenv("OMNIREACH_FORCE_JSON", val)
        assert _should_emit_json(False) is True


def test_should_emit_json_force_env_var_off(monkeypatch):
    """OMNIREACH_FORCE_JSON=0 or empty doesn't force; isatty rules."""
    monkeypatch.setenv("OMNIREACH_FORCE_JSON", "0")
    # In CliRunner (non-TTY), should still emit JSON via isatty path
    monkeypatch.setattr("omnireach.commands.fetch.sys.stdout.isatty", lambda: True)
    assert _should_emit_json(False) is False
