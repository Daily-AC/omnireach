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
        if self.id == "github":
            raise ModuleNotFoundError("omnireach.adapters.github")
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
    res = runner.invoke(main, ["search", "--on", "github,hackernews", "--json", "claude"])
    assert res.exit_code == 0, res.output
    # Warning text appears on stderr (not stdout, because --json is on stdout)
    assert "skip github" in res.stderr
    import json as _json
    parsed = _json.loads(res.stdout)
    assert parsed["query"] == "claude"
    # github was skipped, only hackernews ran
    assert all(r["source"] != "github" for r in parsed["results"])


def test_cli_search_warns_on_unknown_on_source(monkeypatch):
    """--on with a typo should print a warning to stderr (and still run the valid sources)."""
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
    res = runner.invoke(main, ["search", "--on", "hackernews,twiter", "--json", "x"])
    assert res.exit_code == 0, res.output
    assert "未知源" in res.stderr or "未知源" in res.output
    assert "twiter" in res.stderr or "twiter" in res.output


def test_search_includes_active_booster_in_fanout(monkeypatch):
    """When TAVILY_API_KEY is set, tavily MUST be in the fanout source list
    even if the router's MAX_SOURCES cap would exclude it."""
    from omnireach.cli import _augment_with_active_boosters
    from omnireach.registry import load_registry

    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    reg = load_registry()
    # Simulate router returning 5 non-booster sources
    base = ["hackernews", "youtube", "github", "rss"]
    out = _augment_with_active_boosters(base, reg, explicit_sources=None)
    assert "tavily" in out
    assert "brave" not in out
    assert "perplexity" not in out
    assert "exa" not in out
    # Existing entries preserved
    for s in base:
        assert s in out


def test_search_does_not_augment_when_explicit_on(monkeypatch):
    from omnireach.cli import _augment_with_active_boosters
    from omnireach.registry import load_registry

    monkeypatch.setenv("TAVILY_API_KEY", "x")
    reg = load_registry()
    out = _augment_with_active_boosters(["hackernews"], reg, explicit_sources=["hackernews"])
    assert out == ["hackernews"]


def test_search_augment_includes_exa(monkeypatch):
    from omnireach.cli import _augment_with_active_boosters
    from omnireach.registry import load_registry

    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    reg = load_registry()
    out = _augment_with_active_boosters(["hackernews"], reg, explicit_sources=None)
    assert "exa" in out


def test_search_augment_includes_wechat_bilibili_via_exa_key(monkeypatch):
    from omnireach.cli import _augment_with_active_boosters
    from omnireach.registry import load_registry

    monkeypatch.setenv("EXA_API_KEY", "x")
    for k in ("TAVILY_API_KEY", "BRAVE_API_KEY", "PERPLEXITY_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    reg = load_registry()
    out = _augment_with_active_boosters(["hackernews"], reg, explicit_sources=None)
    assert "wechat" in out
    assert "bilibili" in out
    assert "exa" in out


def test_tty_skips_unavailable_errors_and_prints_footer(monkeypatch):
    """Real-user UX bug: unavailable sources should not print ✗ red rows."""
    from click.testing import CliRunner
    from omnireach.cli import main

    # Strip everything except HN — opencli is installed on dev machines, neuter it
    monkeypatch.setattr("shutil.which", lambda b: None)
    for env in ("TAVILY_API_KEY", "BRAVE_API_KEY", "PERPLEXITY_API_KEY", "EXA_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["search", "vibe coding", "--limit", "3", "--timeout", "10"])
    out = result.output
    # No ✗ rows for unavailable sources
    assert "✗ tavily" not in out
    assert "✗ exa" not in out
    assert "✗ wechat" not in out
    assert "✗ youtube" not in out
    # Footer present mentioning doctor / 未配置
    assert "doctor" in out or "未配置" in out


def test_json_output_keeps_unavailable_errors(monkeypatch):
    """JSON output retains all errors with category field, unlike TTY."""
    import json as _json
    from click.testing import CliRunner
    from omnireach.cli import main

    monkeypatch.setattr("shutil.which", lambda b: None)
    for env in ("TAVILY_API_KEY", "BRAVE_API_KEY", "PERPLEXITY_API_KEY", "EXA_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["search", "test", "--limit", "2", "--timeout", "5", "--json"])
    # The output may include warning lines first; find the JSON line
    json_line = next((ln for ln in result.output.splitlines() if ln.strip().startswith("{")), None)
    assert json_line is not None
    data = _json.loads(json_line)
    cats = {e["category"] for e in data.get("errors", [])}
    assert "unavailable" in cats
