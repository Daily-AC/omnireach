from click.testing import CliRunner

from omnireach.cli import main


def test_init_installs_agent_reach_when_missing(monkeypatch):
    called = {"args": None}

    def fake_install(pkg):
        called["args"] = pkg

    monkeypatch.setattr("omnireach.installer.install_pipx_package", fake_install)
    monkeypatch.setattr("omnireach.commands.init.shutil.which", lambda n: None if n == "agent-reach" else "/usr/bin/" + n)

    runner = CliRunner()
    res = runner.invoke(main, ["init", "--yes"])
    assert res.exit_code == 0, res.output
    assert called["args"] == "agent-reach"
    assert "agent-reach" in res.output


def test_init_skips_when_agent_reach_present(monkeypatch):
    def boom_install(pkg):
        raise AssertionError("should not be called")

    monkeypatch.setattr("omnireach.installer.install_pipx_package", boom_install)
    monkeypatch.setattr("omnireach.commands.init.shutil.which", lambda n: "/usr/bin/" + n)

    runner = CliRunner()
    res = runner.invoke(main, ["init", "--yes"])
    assert res.exit_code == 0, res.output
    assert "已安装" in res.output or "already" in res.output.lower()
