from click.testing import CliRunner

from omnireach.cli import main


def test_sources_lists_all_registered():
    runner = CliRunner()
    res = runner.invoke(main, ["sources"])
    assert res.exit_code == 0
    for sid in ["hackernews", "web", "youtube", "github", "rss", "wechat", "bilibili"]:
        assert sid in res.output


def test_sources_groups_by_tier():
    runner = CliRunner()
    res = runner.invoke(main, ["sources"])
    assert "ready" in res.output.lower()


def test_sources_command_shows_booster_section(monkeypatch):
    from click.testing import CliRunner
    from omnireach.cli import main

    monkeypatch.setenv("TAVILY_API_KEY", "x")
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)

    runner = CliRunner()
    result = runner.invoke(main, ["sources"])
    assert result.exit_code == 0
    out = result.output
    assert "💎" in out or "付费增强" in out
    assert "tavily" in out
    assert "已配" in out
    assert "未配" in out
