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
