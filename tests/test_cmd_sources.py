from click.testing import CliRunner

from omnireach.cli import main


def test_sources_lists_all_registered():
    runner = CliRunner()
    res = runner.invoke(main, ["sources"])
    assert res.exit_code == 0
    for sid in ["hackernews", "youtube", "github", "rss", "wechat", "bilibili"]:
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


def test_sources_command_skips_wip_section_when_empty():
    """v0.6: wechat/bilibili promoted out of wip; sources cmd should not render '🚧' section."""
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["sources"])
    assert result.exit_code == 0
    # 🚧 emoji should NOT appear because no source has tier=wip
    assert "🚧" not in result.output
    # And the source list should still include wechat/bilibili under 💎 booster
    assert "wechat" in result.output
    assert "bilibili" in result.output
