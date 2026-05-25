import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.github import GitHubAdapter


def _mock_proc(stdout: bytes, returncode: int = 0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, b""))
    proc.returncode = returncode
    return proc


def test_is_ready_false_without_gh(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    assert asyncio.run(GitHubAdapter().is_ready()) is False


def test_is_ready_true_with_gh(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/gh")
    assert asyncio.run(GitHubAdapter().is_ready()) is True


def test_search_combines_repos_and_issues(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/gh")
    repos = json.dumps([
        {"fullName": "ant/repo", "url": "https://github.com/ant/repo",
         "description": "desc", "stargazersCount": 100, "updatedAt": "2026-05-20T00:00:00Z"}
    ]).encode()
    issues = json.dumps([
        {"title": "issue 1", "url": "https://github.com/x/y/issues/1",
         "body": "body", "author": {"login": "alice"}, "createdAt": "2026-05-21T00:00:00Z"}
    ]).encode()

    async def fake_exec(*args, **kw):
        if "repos" in args:
            return _mock_proc(repos)
        return _mock_proc(issues)

    with patch("omnireach.adapters.github.asyncio.create_subprocess_exec", side_effect=fake_exec):
        out = asyncio.run(GitHubAdapter().search("query", limit=4))
    assert any(r.source == "github" and "ant/repo" in r.url for r in out)
    assert any(r.source == "github" and "/issues/" in r.url for r in out)


def test_search_raises_when_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(GitHubAdapter().search("q"))


def test_search_empty_output(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/gh")
    with patch("omnireach.adapters.github.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_mock_proc(b"[]"))):
        out = asyncio.run(GitHubAdapter().search("q"))
    assert out == []
