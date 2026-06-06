import asyncio
from unittest.mock import patch

import httpx
import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.tweetclaw import TweetClawAdapter


@pytest.fixture
def fixture_payload():
    return {
        "results": [
            {
                "id": "123",
                "text": "OpenClaw agents can search tweets before drafting a reply.",
                "username": "alice",
                "createdAt": "2026-06-06T10:00:00Z",
                "likeCount": 12,
                "retweetCount": 3,
                "replyCount": 2,
                "viewCount": 500,
            }
        ]
    }


def _mock_transport(status: int, json_body: dict | list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        expected = " ".join(("Bearer", "test-api-key"))
        assert request.headers["authorization"] == expected
        assert request.url.path == "/api/v1/x/tweets/search"
        assert request.url.params["q"] == "openclaw"
        assert request.url.params["limit"] == "5"
        return httpx.Response(status, json=json_body or {})

    return httpx.MockTransport(handler)


def test_is_ready_false_without_key(monkeypatch):
    monkeypatch.delenv("XQUIK_API_KEY", raising=False)
    assert asyncio.run(TweetClawAdapter().is_ready()) is False


def test_is_ready_true_with_key(monkeypatch):
    monkeypatch.setenv("XQUIK_API_KEY", "test-api-key")
    assert asyncio.run(TweetClawAdapter().is_ready()) is True


def test_search_returns_normalized_results(monkeypatch, fixture_payload):
    monkeypatch.setenv("XQUIK_API_KEY", "test-api-key")
    real_client = httpx.AsyncClient(transport=_mock_transport(200, fixture_payload))
    with patch("omnireach.adapters.tweetclaw.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(TweetClawAdapter().search("openclaw", limit=5))
    assert len(out) == 1
    assert out[0].source == "tweetclaw"
    assert out[0].adapter == "xquik-api"
    assert out[0].cost == "paid"
    assert out[0].author == "alice"
    assert out[0].url == "https://x.com/alice/status/123"
    assert out[0].engagement.likes == 12
    assert out[0].engagement.shares == 3
    assert out[0].engagement.comments == 2
    assert out[0].engagement.views == 500


def test_search_accepts_tweets_payload_shape(monkeypatch):
    monkeypatch.setenv("XQUIK_API_KEY", "test-api-key")
    payload = {
        "tweets": [
            {
                "tweet_id": "456",
                "full_text": "TweetClaw supports follower export.",
                "author": "@bob",
            }
        ]
    }
    real_client = httpx.AsyncClient(transport=_mock_transport(200, payload))
    with patch("omnireach.adapters.tweetclaw.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(TweetClawAdapter().search("openclaw", limit=5))
    assert len(out) == 1
    assert out[0].title == "TweetClaw supports follower export."
    assert out[0].url == "https://x.com/bob/status/456"


def test_search_uses_custom_base_url(monkeypatch, fixture_payload):
    monkeypatch.setenv("XQUIK_API_KEY", "test-api-key")
    monkeypatch.setenv("XQUIK_BASE_URL", "https://xquik.example")

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("https://xquik.example/api/v1/x/tweets/search")
        return httpx.Response(200, json=fixture_payload)

    real_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("omnireach.adapters.tweetclaw.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(TweetClawAdapter().search("openclaw", limit=5))
    assert len(out) == 1


def test_search_raises_without_key(monkeypatch):
    monkeypatch.delenv("XQUIK_API_KEY", raising=False)
    with pytest.raises(AdapterUnavailable):
        asyncio.run(TweetClawAdapter().search("openclaw"))


def test_search_raises_on_auth_failure(monkeypatch):
    monkeypatch.setenv("XQUIK_API_KEY", "test-api-key")
    real_client = httpx.AsyncClient(transport=_mock_transport(401))
    with patch("omnireach.adapters.tweetclaw.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        with pytest.raises(AdapterUnavailable):
            asyncio.run(TweetClawAdapter().search("openclaw", limit=5))
