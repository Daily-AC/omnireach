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
