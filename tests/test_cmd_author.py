import json

from click.testing import CliRunner

from omnireach.cli import main
from omnireach.contract import (
    AuthorEnvelope,
    AuthorIdentity,
    Engagement,
    SearchResult,
    SourceError,
)

SEC_UID = "MS4wLjABAAAAAAKy2_R6k-oFWT5E-97gbGZQ1laaweQMWImJDkDaef0"


def _envelope(**overrides) -> AuthorEnvelope:
    return AuthorEnvelope(**{
        "query": "彭十六",
        "ts": "2026-09-03T00:00:00Z",
        "author": AuthorIdentity(
            source="douyin", handle="彭十六", id=SEC_UID, name="彭十六elf",
            url=f"https://www.douyin.com/user/{SEC_UID}", followers=28195000,
            resolved_from="search",
        ),
        "order": "likes",
        "scanned": 355,
        "complete": True,
        "results": [SearchResult(
            source="douyin", adapter="native-chrome", title="把东方美学带到欧洲",
            url="https://www.douyin.com/video/7267478481213181238",
            ts="2023-08-15T09:28:24.000Z",
            engagement=Engagement(likes=6534100),
        )],
        **overrides,
    })


def _stub(monkeypatch, envelope):
    captured = {}

    async def fake_catalog(handle, **kwargs):
        captured.update({"handle": handle, **kwargs})
        return envelope

    monkeypatch.setattr("omnireach.commands.author.author_catalog", fake_catalog)
    return captured


def test_author_json_forwards_every_option(monkeypatch):
    captured = _stub(monkeypatch, _envelope())

    result = CliRunner().invoke(main, [
        "author", "彭十六",
        "--limit", "50",
        "--order", "likes",
        "--include-media-urls",
        "--timeout", "300",
        "--json",
    ])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["author"]["id"] == SEC_UID
    assert payload["scanned"] == 355
    assert payload["results"][0]["engagement"]["likes"] == 6534100
    assert captured == {
        "handle": "彭十六",
        "source": "douyin",
        "limit": 50,
        "order": "likes",
        "include_media_urls": True,
        "timeout": 300.0,
    }


def test_author_tty_table_shows_likes_and_warnings(monkeypatch):
    _stub(monkeypatch, _envelope(warnings=["Resolved by follower count"]))
    monkeypatch.setattr(
        "omnireach.commands.author._emit_json", lambda explicit: explicit,
    )

    result = CliRunner().invoke(main, ["author", "彭十六"])

    assert result.exit_code == 0
    assert "彭十六elf" in result.output
    assert "6,534,100" in result.output
    assert "Resolved by follower count" in result.output


def test_author_exits_nonzero_when_the_catalog_failed(monkeypatch):
    _stub(monkeypatch, _envelope(
        author=None,
        results=[],
        errors=[SourceError(
            source="douyin",
            error="the connected Chrome extension does not implement douyin.author",
            category="unavailable",
        )],
    ))

    result = CliRunner().invoke(main, ["author", "彭十六", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.output)["errors"][0]["category"] == "unavailable"


def test_unknown_source_is_a_usage_error():
    result = CliRunner().invoke(main, ["author", "x", "--source", "youtube"])

    assert result.exit_code == 2
    assert "youtube" in result.output
