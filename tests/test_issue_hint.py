"""Tests for v0.6.2: issue link surfaced on failed errors + global exception handler."""

import pytest

from omnireach.cli import ISSUE_URL


def test_issue_url_points_to_repo():
    assert ISSUE_URL == "https://github.com/Daily-AC/omnireach/issues/new/choose"


def test_entrypoint_catches_uncaught_exception_and_exits_2(monkeypatch):
    """Unhandled exception inside main() → entrypoint catches, exits 2 (not bare crash)."""
    import omnireach.cli as cli_mod

    def boom_main(*args, **kwargs):
        raise RuntimeError("synthetic crash")

    monkeypatch.setattr(cli_mod.main, "main", boom_main)

    with pytest.raises(SystemExit) as excinfo:
        cli_mod._entrypoint()
    assert excinfo.value.code == 2


def test_entrypoint_handles_keyboard_interrupt(monkeypatch):
    """Ctrl+C → entrypoint exits 130 cleanly."""
    import omnireach.cli as cli_mod

    def kb_main(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(cli_mod.main, "main", kb_main)

    with pytest.raises(SystemExit) as excinfo:
        cli_mod._entrypoint()
    assert excinfo.value.code == 130


def test_entrypoint_passes_through_systemexit(monkeypatch):
    """Normal exit (click sys.exit) is re-raised unchanged."""
    import omnireach.cli as cli_mod

    def normal_main(*args, **kwargs):
        raise SystemExit(0)

    monkeypatch.setattr(cli_mod.main, "main", normal_main)

    with pytest.raises(SystemExit) as excinfo:
        cli_mod._entrypoint()
    assert excinfo.value.code == 0


def test_search_renders_issue_hint_when_failed_errors(monkeypatch):
    """End-to-end: when a real adapter raises non-AdapterUnavailable, TTY shows issue hint."""
    from click.testing import CliRunner
    from omnireach.adapters.base import AdapterBase
    from omnireach.cli import main
    from omnireach.contract import SearchResult

    class _Crash(AdapterBase):
        name = "hackernews"  # mimic an existing source so router picks it
        async def is_ready(self):
            return True
        async def search(self, query, *, limit=10):
            raise RuntimeError("synthetic crash inside adapter")

    # Patch the HN spec's adapter loader to return our _Crash class
    import omnireach.registry as reg_mod
    original_load = reg_mod.SourceSpec.load_adapter_class

    def fake_load(self):
        if self.id == "hackernews":
            return _Crash
        return original_load(self)

    monkeypatch.setattr(reg_mod.SourceSpec, "load_adapter_class", fake_load)
    # v0.9.2: force TTY-render branch (CliRunner stdout is non-TTY by default)
    monkeypatch.setattr("omnireach.cli._should_emit_json", lambda flag: flag)
    # Also strip every other source so HN is the only path
    monkeypatch.setattr("shutil.which", lambda b: None)
    for env in ("TAVILY_API_KEY", "BRAVE_API_KEY", "PERPLEXITY_API_KEY", "EXA_API_KEY"):
        monkeypatch.delenv(env, raising=False)

    runner = CliRunner()
    result = runner.invoke(main, ["search", "test", "--limit", "1", "--on", "hackernews", "--timeout", "5"])
    assert "✗ hackernews" in result.output
    assert "github.com/Daily-AC/omnireach/issues" in result.output
    assert "提 issue" in result.output
