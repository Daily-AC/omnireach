import json

from click.testing import CliRunner

from omnireach.cli import main


def test_cli_help():
    runner = CliRunner()
    res = runner.invoke(main, ["--help"])
    assert res.exit_code == 0
    assert "search" in res.output


def test_cli_search_on_hackernews_only_smoke(monkeypatch):
    """Smoke test — uses --on hackernews + monkeypatched search to avoid real network."""
    import omnireach.adapters.hackernews as hn

    async def fake_search(self, query, *, limit=10):
        from omnireach.contract import SearchResult
        return [
            SearchResult(
                source="hackernews",
                adapter="builtin",
                title=f"fake {query}",
                url="https://e.x/1",
                ts="2026-05-25T12:00:00Z",
                score=0.7,
            )
        ]

    monkeypatch.setattr(hn.HackerNewsAdapter, "search", fake_search)

    runner = CliRunner()
    res = runner.invoke(main, ["search", "--on", "hackernews", "--json", "claude"])
    assert res.exit_code == 0, res.output
    parsed = json.loads(res.output)
    assert parsed["query"] == "claude"
    assert parsed["results"][0]["source"] == "hackernews"


def test_cli_search_skips_broken_adapter(monkeypatch):
    """When an adapter fails to load (e.g. ModuleNotFoundError), CLI logs a warning
    on stderr and continues with whatever remaining adapters loaded."""

    from omnireach import registry as reg_mod
    original_load = reg_mod.SourceSpec.load_adapter_class

    def maybe_broken(self):
        if self.id == "web":
            raise ModuleNotFoundError("omnireach.adapters.web")
        return original_load(self)

    monkeypatch.setattr(reg_mod.SourceSpec, "load_adapter_class", maybe_broken)

    # Stub hackernews so we don't hit network
    import omnireach.adapters.hackernews as hn

    async def fake_search(self, query, *, limit=10):
        from omnireach.contract import SearchResult
        return [
            SearchResult(
                source="hackernews",
                adapter="builtin",
                title="ok",
                url="https://e.x/1",
                ts="2026-05-25T12:00:00Z",
                score=0.5,
            )
        ]

    monkeypatch.setattr(hn.HackerNewsAdapter, "search", fake_search)

    runner = CliRunner()
    res = runner.invoke(main, ["search", "--on", "web,hackernews", "--json", "claude"])
    assert res.exit_code == 0, res.output
    # Warning text appears on stderr (not stdout, because --json is on stdout)
    assert "skip web" in res.stderr
    import json as _json
    parsed = _json.loads(res.stdout)
    assert parsed["query"] == "claude"
    # web was skipped, only hackernews ran
    assert all(r["source"] != "web" for r in parsed["results"])
