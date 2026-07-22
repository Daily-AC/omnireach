import json

from click.testing import CliRunner

from omnireach.cli import main
from omnireach.media.contract import MediaEnvelope


def test_media_help_exposes_inspect_parse_and_download():
    result = CliRunner().invoke(main, ["media", "--help"])

    assert result.exit_code == 0
    assert "inspect" in result.output
    assert "parse" in result.output
    assert "download" in result.output


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


def test_media_download_maps_cli_limits_and_cookie_profile(monkeypatch, tmp_path):
    captured = {}

    def fake_download(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return MediaEnvelope(
            ok=True,
            url=url,
            source="douyin",
            media_type="video",
            backend="yt-dlp",
            mode="download",
            parsed_at="2026-07-22T00:00:00Z",
        )

    monkeypatch.setattr("omnireach.commands.media.download_media", fake_download)
    result = CliRunner().invoke(main, [
        "media", "download", "https://www.douyin.com/video/123",
        "--quality", "small",
        "--cookies-from-browser", "chrome:Profile 1",
        "--output-dir", str(tmp_path),
        "--max-size-mb", "25",
        "--timeout", "90",
        "--json",
    ])

    assert result.exit_code == 0
    assert json.loads(result.output)["mode"] == "download"
    assert captured == {
        "url": "https://www.douyin.com/video/123",
        "quality": "small",
        "cookies_from_browser": "chrome:Profile 1",
        "output_dir": tmp_path,
        "reuse_cache": True,
        "max_bytes": 25 * 1024 * 1024,
        "timeout": 90.0,
    }
