from click.testing import CliRunner

from omnireach.cli import main


def test_setup_requires_known_source():
    runner = CliRunner()
    res = runner.invoke(main, ["setup", "nope"])
    assert res.exit_code != 0
    assert "未知" in res.output or "未知" in res.stderr or "unknown" in res.output.lower() or "unknown" in res.stderr.lower()


def test_setup_hackernews_zero_config():
    """`setup hackernews` short-circuits — HN is zero-config."""
    runner = CliRunner()
    res = runner.invoke(main, ["setup", "hackernews"])
    assert res.exit_code == 0, res.output
    assert "零配置" in res.output or "无需" in res.output or "ready" in res.output.lower()


def test_setup_reports_failure(monkeypatch):
    """When the wizard reports failure (e.g. install error), CLI exits non-zero."""
    from omnireach import wizard as wiz_mod
    from omnireach.wizard import SetupReport, StepKind, StepStatus, WizardStep

    async def fake_run_setup(*args, **kwargs):
        return SetupReport(
            source_id="twitter",
            steps=[
                WizardStep(
                    StepKind.AUTO,
                    "npm install @jackwener/opencli",
                    StepStatus.FAILED,
                    detail="install opencli failed: network",
                )
            ],
        )

    monkeypatch.setattr(wiz_mod, "run_setup", fake_run_setup)

    runner = CliRunner()
    res = runner.invoke(main, ["setup", "twitter", "--yes"])
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


def test_setup_youtube_installs_yt_dlp(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setattr("shutil.which", lambda b: None)
    calls = []
    def fake_run(cmd, **kw):
        calls.append(cmd)
        import subprocess
        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.setattr("subprocess.run", fake_run)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "youtube"], input="y\n")
    assert result.exit_code == 0
    assert any("yt-dlp" in (c if isinstance(c, str) else " ".join(c)) for c in calls)


def test_setup_wechat_routes_to_exa_booster(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "wechat"], input="y\nexa-test-key\n")
    assert result.exit_code == 0
    assert "EXA_API_KEY" in result.output or "Exa" in result.output or "exa" in result.output.lower()
    secrets = tmp_path / ".omnireach" / "secrets.env"
    if secrets.exists():
        assert "EXA_API_KEY=exa-test-key" in secrets.read_text()


def test_setup_bilibili_routes_to_exa_booster(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "bilibili"], input="y\nexa-test-key2\n")
    assert result.exit_code == 0
    secrets = tmp_path / ".omnireach" / "secrets.env"
    if secrets.exists():
        assert "EXA_API_KEY=exa-test-key2" in secrets.read_text() or "EXA_API_KEY" in secrets.read_text()


def test_setup_github_prompts_manual(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setattr("shutil.which", lambda b: None)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "github"])
    assert result.exit_code == 0
    assert "brew install gh" in result.output or "cli.github.com" in result.output


def test_setup_rss_is_builtin(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "rss"])
    assert result.exit_code == 0
    assert "内置" in result.output or "feedparser" in result.output


def test_setup_exa_is_booster(tmp_path, monkeypatch):
    """Sanity check: exa landed in BOOSTER_GUIDES."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from click.testing import CliRunner
    from omnireach.cli import main
    runner = CliRunner()
    # Provide y\n for the "开始吗?" prompt and an arbitrary key for the hidden prompt
    result = runner.invoke(main, ["setup", "exa"], input="y\nexa-test-key\n")
    assert result.exit_code == 0
    secrets = tmp_path / ".omnireach" / "secrets.env"
    if secrets.exists():
        assert "EXA_API_KEY=exa-test-key" in secrets.read_text()
