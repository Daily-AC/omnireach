from click.testing import CliRunner

from omnireach.cli import main


def test_setup_requires_known_source():
    runner = CliRunner()
    res = runner.invoke(main, ["setup", "nope"])
    assert res.exit_code != 0
    assert "未知" in res.output or "未知" in res.stderr or "unknown" in res.output.lower() or "unknown" in res.stderr.lower()


def test_setup_runs_wizard_on_known_source():
    """`setup hackernews --yes` should succeed immediately since HN is_ready=True."""
    runner = CliRunner()
    res = runner.invoke(main, ["setup", "hackernews", "--yes"])
    assert res.exit_code == 0, res.output
    assert "已就绪" in res.output or "ready" in res.output.lower()


def test_setup_reports_failure(monkeypatch):
    """When the wizard reports failure (e.g. install error), CLI exits non-zero."""
    from omnireach import wizard as wiz_mod
    from omnireach.wizard import SetupReport, StepKind, StepStatus, WizardStep

    async def fake_run_setup(*args, **kwargs):
        return SetupReport(
            source_id="reddit",
            steps=[
                WizardStep(
                    StepKind.AUTO,
                    "npm install rdt-cli",
                    StepStatus.FAILED,
                    detail="install rdt-cli failed: network",
                )
            ],
        )

    monkeypatch.setattr(wiz_mod, "run_setup", fake_run_setup)

    runner = CliRunner()
    res = runner.invoke(main, ["setup", "hackernews", "--yes"])
    assert res.exit_code == 1
    assert "失败" in res.output or "failed" in res.output.lower()


def test_setup_tavily_writes_secrets_env(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "tavily"], input="y\ntvly-abc123\n")
    assert result.exit_code == 0
    secrets = tmp_path / ".omnireach" / "secrets.env"
    assert secrets.exists()
    assert "TAVILY_API_KEY=tvly-abc123" in secrets.read_text()
    mode = secrets.stat().st_mode & 0o777
    assert mode == 0o600
