import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.reddit import RedditAdapter


def _mock_proc(stdout: bytes, stderr: bytes = b"", returncode: int = 0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    return proc


def test_is_ready_false_without_rdt(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    assert asyncio.run(RedditAdapter().is_ready()) is False


def test_is_ready_true_with_rdt(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/rdt-cli")
    assert asyncio.run(RedditAdapter().is_ready()) is True


def test_search_parses_results(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/rdt-cli")
    payload = json.dumps({
        "results": [
            {
                "title": "Post 1",
                "permalink": "/r/python/comments/abc/post_1",
                "selftext": "body",
                "author": "alice",
                "created_utc": 1716000000,
                "score": 42,
                "num_comments": 7,
                "subreddit": "python",
            },
        ]
    }).encode()
    with patch("omnireach.adapters.reddit.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_mock_proc(payload))):
        out = asyncio.run(RedditAdapter().search("python", limit=5))
    assert len(out) == 1
    assert out[0].source == "reddit"
    assert out[0].title == "Post 1"
    assert "reddit.com/r/python/comments/abc" in out[0].url
    assert out[0].author == "alice"
    assert out[0].engagement.likes == 42
    assert out[0].engagement.comments == 7


def test_search_raises_when_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(RedditAdapter().search("q"))


def test_search_detects_unauth_error(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/rdt-cli")
    with patch("omnireach.adapters.reddit.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_mock_proc(b"", b"not logged in: run `rdt login`", 1))):
        with pytest.raises(AdapterUnavailable) as exc:
            asyncio.run(RedditAdapter().search("q"))
        assert "login" in str(exc.value).lower() or "rdt" in str(exc.value).lower()
