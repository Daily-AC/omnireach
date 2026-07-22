import json
from pathlib import Path
from unittest.mock import MagicMock

from omnireach.media.service import inspect_media, parse_media


FIXTURES = Path(__file__).parent / "fixtures"
YTDLP_PAYLOAD = json.loads(
    (FIXTURES / "ytdlp_youtube_captioned_sanitized.json").read_text()
)


def _fake_ytdlp(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda tool: f"/usr/bin/{tool}")

    def fake_run(command, **kwargs):
        if command == ["yt-dlp", "--version"]:
            return MagicMock(returncode=0, stdout="2026.06.09\n", stderr="")
        return MagicMock(returncode=0, stdout=json.dumps(YTDLP_PAYLOAD), stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)


def test_ytdlp_inspect_normalizes_shape_without_leaking_signed_urls(monkeypatch):
    _fake_ytdlp(monkeypatch)

    envelope = inspect_media("https://www.youtube.com/watch?v=abc")
    serialized = envelope.model_dump_json()

    assert envelope.ok is True
    assert envelope.source == "youtube"
    assert envelope.metadata.duration_ms == 213000
    assert {(track.language, track.source) for track in envelope.tracks} == {
        ("en", "publisher"),
        ("de-DE", "publisher"),
        ("en-orig", "automatic"),
        ("zh-Hans", "automatic"),
    }
    assert "token=secret" not in serialized
    assert "signed.example" not in serialized
    assert envelope.artifacts == []


def test_ytdlp_public_track_listing_is_bounded(monkeypatch):
    _fake_ytdlp(monkeypatch)
    automatic = {
        f"lang-{index}": [{
            "ext": "vtt",
            "url": f"https://signed.example/{index}?token=secret",
        }]
        for index in range(100)
    }
    payload = dict(YTDLP_PAYLOAD, subtitles={}, automatic_captions=automatic)
    monkeypatch.setattr(
        "subprocess.run",
        lambda command, **kwargs: MagicMock(
            returncode=0,
            stdout="2026.06.09\n" if command == ["yt-dlp", "--version"] else json.dumps(payload),
            stderr="",
        ),
    )

    envelope = inspect_media("https://www.youtube.com/watch?v=abc")

    assert len(envelope.tracks) == 40
    assert "omitted 60 languages" in envelope.warnings[0]


def test_ytdlp_http_412_is_a_blocked_error(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(
        "subprocess.run",
        lambda command, **kwargs: MagicMock(
            returncode=1,
            stdout="",
            stderr="HTTP Error 412: Precondition Failed",
        ),
    )

    envelope = inspect_media(
        "https://www.bilibili.com/video/BV1R1e4zKEh1",
        backend="yt-dlp",
    )

    assert envelope.ok is False
    assert envelope.errors[0].category == "blocked"
    assert "authenticated backend" in envelope.errors[0].hint


def test_ytdlp_ssl_eof_is_retryable(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(
        "subprocess.run",
        lambda command, **kwargs: MagicMock(
            returncode=1,
            stdout="",
            stderr="SSL: UNEXPECTED_EOF_WHILE_READING",
        ),
    )

    envelope = inspect_media("https://www.youtube.com/watch?v=abc")

    assert envelope.ok is False
    assert envelope.errors[0].retryable is True
    assert "retry" in envelope.errors[0].hint.lower()


def test_quick_parse_writes_transcript_and_manifest(monkeypatch, tmp_path):
    _fake_ytdlp(monkeypatch)
    response = MagicMock(
        content=b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello world\n",
        encoding="utf-8",
        headers={},
    )
    response.raise_for_status.return_value = None
    monkeypatch.setattr("omnireach.media.service.httpx.get", lambda *args, **kwargs: response)

    envelope = parse_media(
        "https://www.youtube.com/watch?v=abc",
        language="en",
        output_dir=tmp_path,
    )

    assert envelope.ok is True
    assert envelope.transcript.text_preview == "Hello world"
    kinds = {artifact.kind for artifact in envelope.artifacts}
    assert kinds == {
        "metadata", "subtitle", "transcript_json", "transcript_markdown", "manifest",
    }
    assert all(artifact.path.startswith(str(tmp_path)) for artifact in envelope.artifacts)
    assert "signed.example" not in (tmp_path / "manifest.json").read_text()
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert {artifact["kind"] for artifact in manifest["artifacts"]} == {
        "metadata", "subtitle", "transcript_json", "transcript_markdown",
    }


def test_quick_parse_without_captions_is_success_with_warning(monkeypatch, tmp_path):
    _fake_ytdlp(monkeypatch)
    payload = dict(YTDLP_PAYLOAD, subtitles={}, automatic_captions={})
    monkeypatch.setattr(
        "subprocess.run",
        lambda command, **kwargs: MagicMock(
            returncode=0,
            stdout="2026.06.09\n" if command == ["yt-dlp", "--version"] else json.dumps(payload),
            stderr="",
        ),
    )

    envelope = parse_media("https://www.youtube.com/watch?v=abc", output_dir=tmp_path)

    assert envelope.ok is True
    assert envelope.transcript is None
    assert envelope.warnings == ["No supported subtitle track is available"]
    assert {artifact.kind for artifact in envelope.artifacts} == {"metadata", "manifest"}


def test_subtitle_size_limit_is_structured_failure(monkeypatch, tmp_path):
    _fake_ytdlp(monkeypatch)
    response = MagicMock(
        content=b"",
        encoding="utf-8",
        headers={"content-length": str(21 * 1024 * 1024)},
    )
    response.raise_for_status.return_value = None
    monkeypatch.setattr("omnireach.media.service.httpx.get", lambda *args, **kwargs: response)

    envelope = parse_media(
        "https://www.youtube.com/watch?v=abc",
        language="en",
        output_dir=tmp_path,
    )

    assert envelope.ok is False
    assert envelope.errors[0].category == "limit"
    assert envelope.errors[0].stage == "subtitle"


def test_direct_inspect_uses_ffprobe(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda tool: "/usr/bin/ffprobe")
    payload = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 640, "height": 360},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"duration": "2.5", "tags": {"title": "Direct sample"}},
    }
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: MagicMock(returncode=0, stdout=json.dumps(payload), stderr=""),
    )

    envelope = inspect_media("https://media.example/sample.mp4")

    assert envelope.backend == "direct"
    assert envelope.media_type == "video"
    assert envelope.metadata.duration_ms == 2500
    assert envelope.metadata.codec == "h264"


def test_bilibili_auto_backend_uses_public_api(monkeypatch):
    fixture = json.loads((FIXTURES / "bilibili_media_responses.json").read_text())
    view_response = MagicMock()
    view_response.raise_for_status.return_value = None
    view_response.json.return_value = fixture["view"]
    player_response = MagicMock()
    player_response.raise_for_status.return_value = None
    player_with_subtitle = fixture["player"]
    player_with_subtitle["data"]["subtitle"]["subtitles"] = [{
        "lan": "zh-CN",
        "subtitle_url": "//i0.hdsl.com/subtitle/sample.json",
    }]
    player_response.json.return_value = player_with_subtitle
    monkeypatch.setattr(
        "omnireach.media.service.httpx.get",
        lambda url, **kwargs: player_response if "/x/player/" in url else view_response,
    )

    envelope = inspect_media("https://www.bilibili.com/video/BV1R1e4zKEh1")

    assert envelope.ok is True
    assert envelope.backend == "bilibili-api"
    assert envelope.metadata.title.startswith("【4KHDR")
    assert envelope.tracks[0].language == "zh-CN"
