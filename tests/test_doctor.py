from click.testing import CliRunner

from omnireach.cli import main
from omnireach.doctor import run_doctor


async def test_run_doctor_returns_status_per_source():
    statuses = await run_doctor()
    ids = [s.source for s in statuses]
    assert "hackernews" in ids
    hn = next(s for s in statuses if s.source == "hackernews")
    assert hn.ok is True


def test_doctor_cli_runs():
    runner = CliRunner()
    res = runner.invoke(main, ["doctor"])
    # exit_code may be 0 (all green) or 1 (some sources fail), but output must render
    assert res.exit_code in (0, 1)
    assert "hackernews" in res.output
