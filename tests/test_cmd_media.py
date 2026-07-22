import json

from click.testing import CliRunner

from omnireach.cli import main
from omnireach.media.contract import MediaEnvelope


def test_media_help_exposes_inspect_and_parse():
    result = CliRunner().invoke(main, ["media", "--help"])

    assert result.exit_code == 0
    assert "inspect" in result.output
    assert "parse" in result.output


def test_media_parse_help_documents_explicit_browser_cookies():
    result = CliRunner().invoke(main, ["media", "parse", "--help"])

    assert result.exit_code == 0
    assert "--cookies-from-browser" in result.output


def test_media_inspect_json(monkeypatch):
    monkeypatch.setattr(
        "omnireach.commands.media.inspect_media",
        lambda url, **kwargs: MediaEnvelope(
            ok=True,
            url=url,
            source="youtube",
            media_type="video",
            backend="yt-dlp",
            mode="inspect",
            parsed_at="2026-07-22T00:00:00Z",
        ),
    )

    result = CliRunner().invoke(
        main, ["media", "inspect", "https://youtu.be/abc", "--json"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["source"] == "youtube"


def test_media_failure_keeps_json_and_exits_nonzero(monkeypatch):
    monkeypatch.setattr(
        "omnireach.commands.media.inspect_media",
        lambda url, **kwargs: MediaEnvelope(
            ok=False,
            url=url,
            source="youtube",
            media_type="unknown",
            backend="yt-dlp",
            mode="inspect",
            parsed_at="2026-07-22T00:00:00Z",
        ),
    )

    result = CliRunner().invoke(
        main, ["media", "inspect", "https://youtu.be/missing", "--json"],
    )

    assert result.exit_code == 1
    assert json.loads(result.output)["ok"] is False
