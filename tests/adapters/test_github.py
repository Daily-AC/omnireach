import json

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.github import GitHubAdapter


async def test_github_search_parses_agent_reach_json(monkeypatch):
    fake = json.dumps({
        "results": [
            {
                "title": "Daily-AC/omnireach",
                "url": "https://github.com/Daily-AC/omnireach",
                "description": "全网通搜索 CLI + Skill",
                "stars": 42,
                "kind": "repo",
                "updated_at": "2026-05-25T00:00:00Z",
            }
        ]
    })

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0
            async def communicate(self):
                return (fake.encode(), b"")
        return P()

    monkeypatch.setattr("omnireach.adapters.github.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.github.shutil.which", lambda n: "/usr/bin/agent-reach")

    out = await GitHubAdapter().search("omnireach", limit=3)
    assert out[0].source == "github"
    assert out[0].engagement.likes == 42


async def test_github_missing_binary(monkeypatch):
    monkeypatch.setattr("omnireach.adapters.github.shutil.which", lambda n: None)
    with pytest.raises(AdapterUnavailable):
        await GitHubAdapter().search("x")
