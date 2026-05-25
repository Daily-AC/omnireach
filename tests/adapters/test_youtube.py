import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.youtube import YouTubeAdapter


def _mock_proc(stdout: bytes, stderr: bytes = b"", returncode: int = 0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    return proc


def test_is_ready_false_without_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    assert asyncio.run(YouTubeAdapter().is_ready()) is False


def test_is_ready_true_with_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/yt-dlp")
    assert asyncio.run(YouTubeAdapter().is_ready()) is True


def test_search_parses_jsonl(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/yt-dlp")
    payload = "\n".join([
        json.dumps({"title": "Vid 1", "url": "https://youtu.be/a", "uploader": "alice", "timestamp": 1716000000, "view_count": 100}),
        json.dumps({"title": "Vid 2", "webpage_url": "https://youtu.be/b", "uploader": "bob", "view_count": 50}),
    ]).encode()
    with patch("omnireach.adapters.youtube.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_mock_proc(payload))):
        out = asyncio.run(YouTubeAdapter().search("claude", limit=5))
    assert len(out) == 2
    assert out[0].source == "youtube"
    assert out[0].title == "Vid 1"
    assert out[0].url == "https://youtu.be/a"
    assert out[0].author == "alice"
    assert out[0].engagement.views == 100
    assert out[1].url == "https://youtu.be/b"


def test_search_raises_when_binary_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(YouTubeAdapter().search("q"))


def test_search_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/yt-dlp")
    with patch("omnireach.adapters.youtube.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_mock_proc(b"", b"boom", 1))):
        with pytest.raises(AdapterUnavailable):
            asyncio.run(YouTubeAdapter().search("q"))


def test_search_skips_blank_lines(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/yt-dlp")
    payload = b'\n{"title":"x","url":"https://y/x"}\n\n'
    with patch("omnireach.adapters.youtube.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_mock_proc(payload))):
        out = asyncio.run(YouTubeAdapter().search("q"))
    assert len(out) == 1
