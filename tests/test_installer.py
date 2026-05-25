import shutil
import subprocess

import pytest

from omnireach.installer import (
    InstallError,
    ensure_binary,
    install_pipx_package,
)


def test_ensure_binary_returns_path_when_present(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)
    assert ensure_binary("git") == "/usr/bin/git"


def test_ensure_binary_raises_when_missing(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(InstallError) as exc:
        ensure_binary("not-real-bin", hint="安装它")
    assert "not-real-bin" in str(exc.value)


def test_install_pipx_package_invokes_pipx(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pipx")
    install_pipx_package("agent-reach")
    assert calls and calls[0][:3] == ["pipx", "install", "agent-reach"]


def test_install_pipx_raises_on_failure(monkeypatch):
    def fake_run(args, **kwargs):
        class R:
            returncode = 1
            stdout = ""
            stderr = "boom"

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pipx")
    with pytest.raises(InstallError):
        install_pipx_package("agent-reach")
