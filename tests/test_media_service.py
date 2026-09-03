import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx

from omnireach.media.contract import MediaEnvelope
from omnireach.media.service import (
    _RETRY_ATTEMPTS,
    download_media,
    inspect_media,
    parse_media,
)


FIXTURES = Path(__file__).parent / "fixtures"
YTDLP_PAYLOAD = json.loads(
    (FIXTURES / "ytdlp_youtube_captioned_sanitized.json").read_text()
)
BILIBILI_YTDLP_PAYLOAD = json.loads(
    (FIXTURES / "ytdlp_bilibili_captioned_sanitized.json").read_text()
)
DOUYIN_YTDLP_PAYLOAD = json.loads(
    (FIXTURES / "ytdlp_douyin_sanitized.json").read_text()
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


def test_douyin_download_writes_bounded_h264_artifact(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(
        "omnireach.media.service._ytdlp_payload",
        lambda *args, **kwargs: DOUYIN_YTDLP_PAYLOAD,
    )
    monkeypatch.setattr(
        "omnireach.media.service._yt_dlp_version",
        lambda timeout: "2026.06.09",
    )

    def fake_download(command, timeout):
        commands.append(command)
        template = Path(command[command.index("--output") + 1])
        path = Path(str(template).replace("%(ext)s", "mp4"))
        path.write_bytes(b"downloaded-douyin-video")
        return path.resolve()

    monkeypatch.setattr("omnireach.media.service._run_download", fake_download)

    envelope = download_media(
        "https://www.douyin.com/video/7664188112177079482",
        cookies_from_browser="chrome:Profile 1",
        output_dir=tmp_path,
        max_bytes=20 * 1024 * 1024,
    )

    assert envelope.ok is True
    assert envelope.source == "douyin"
    assert envelope.mode == "download"
    assert envelope.metadata.codec == "h264"
    media = next(item for item in envelope.artifacts if item.kind == "media")
    assert media.bytes == len(b"downloaded-douyin-video")
    assert Path(media.path).read_bytes() == b"downloaded-douyin-video"
    assert commands[0][commands[0].index("--format") + 1] == "h264_720p_441058-0"
    assert commands[0][commands[0].index("--max-filesize") + 1] == str(20 * 1024 * 1024)
    serialized = envelope.model_dump_json()
    assert "Profile 1" not in serialized
    assert "cookie" not in serialized.casefold()
    assert "x-signature" not in serialized
    assert "signed.example" not in serialized
    assert envelope.metadata.thumbnail_url is None
    assert "Signed thumbnail URL omitted" in envelope.warnings[0]


def test_douyin_download_reuses_hash_verified_cache(monkeypatch, tmp_path):
    calls = 0
    monkeypatch.setattr(
        "omnireach.media.service._ytdlp_payload",
        lambda *args, **kwargs: DOUYIN_YTDLP_PAYLOAD,
    )
    monkeypatch.setattr(
        "omnireach.media.service._yt_dlp_version",
        lambda timeout: "2026.06.09",
    )

    def fake_download(command, timeout):
        nonlocal calls
        calls += 1
        template = Path(command[command.index("--output") + 1])
        path = Path(str(template).replace("%(ext)s", "mp4"))
        path.write_bytes(b"cached-douyin-video")
        return path.resolve()

    monkeypatch.setattr("omnireach.media.service._run_download", fake_download)
    kwargs = {
        "cookies_from_browser": "chrome:Profile 1",
        "output_dir": tmp_path,
        "max_bytes": 20 * 1024 * 1024,
    }

    first = download_media(
        "https://www.douyin.com/video/7664188112177079482", **kwargs,
    )
    second = download_media(
        "https://www.douyin.com/video/7664188112177079482", **kwargs,
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert calls == 1


def test_douyin_download_rejects_formats_over_size_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "omnireach.media.service._ytdlp_payload",
        lambda *args, **kwargs: DOUYIN_YTDLP_PAYLOAD,
    )
    monkeypatch.setattr(
        "omnireach.media.service._run_download",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not download")),
    )

    envelope = download_media(
        "https://www.douyin.com/video/7664188112177079482",
        output_dir=tmp_path,
        max_bytes=5 * 1024 * 1024,
    )

    assert envelope.ok is False
    assert envelope.errors[0].category == "limit"
    assert "smallest downloadable MP4" in envelope.errors[0].message


def test_douyin_download_explains_fresh_cookie_requirement(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "omnireach.media.service._ytdlp_payload",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("Fresh cookies (not necessarily logged in) are needed")
        ),
    )

    envelope = download_media(
        "https://www.douyin.com/video/7664188112177079482",
        output_dir=tmp_path,
    )

    assert envelope.ok is False
    assert envelope.errors[0].category == "blocked"
    assert "--cookies-from-browser" in envelope.errors[0].hint


def test_media_download_rejects_non_douyin_url(tmp_path):
    envelope = download_media(
        "https://www.youtube.com/watch?v=abc", output_dir=tmp_path,
    )

    assert envelope.ok is False
    assert envelope.errors[0].category == "invalid"


def test_bilibili_browser_cookies_select_ytdlp_and_inline_subtitles(
    monkeypatch, tmp_path,
):
    commands = []
    monkeypatch.setattr("shutil.which", lambda tool: f"/usr/bin/{tool}")

    def fake_run(command, **kwargs):
        commands.append(command)
        if command == ["yt-dlp", "--version"]:
            return MagicMock(returncode=0, stdout="2026.06.09\n", stderr="")
        return MagicMock(
            returncode=0,
            stdout=json.dumps(BILIBILI_YTDLP_PAYLOAD),
            stderr="",
        )

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(
        "omnireach.media.service.httpx.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("inline subtitles must not trigger an HTTP fetch")
        ),
    )

    envelope = parse_media(
        "https://www.bilibili.com/video/BV12N4y1M7rh",
        cookies_from_browser="chrome:Profile 1",
        language="zh-Hans",
        output_dir=tmp_path,
    )

    assert envelope.ok is True
    assert envelope.backend == "yt-dlp"
    assert envelope.transcript.segment_count == 3
    assert envelope.transcript.text_preview.startswith("你好\n我是小夫")
    inspect_command = next(command for command in commands if "--dump-single-json" in command)
    assert inspect_command[-3:] == [
        "--cookies-from-browser",
        "chrome:Profile 1",
        "https://www.bilibili.com/video/BV12N4y1M7rh",
    ]
    assert "chrome:Profile 1" not in envelope.model_dump_json()
    assert "chrome:Profile 1" not in (tmp_path / "manifest.json").read_text()


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


def test_subtitle_network_failure_has_retry_hint(monkeypatch, tmp_path):
    _fake_ytdlp(monkeypatch)
    monkeypatch.setattr(
        "omnireach.media.service.httpx.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            httpx.ConnectError("SSL EOF")
        ),
    )

    envelope = parse_media(
        "https://www.youtube.com/watch?v=abc",
        language="en",
        output_dir=tmp_path,
    )

    error = envelope.errors[0]
    assert error.retryable is True
    assert "retry the same command" in error.hint
    assert "language" not in error.hint


def test_quick_parse_reuses_hash_verified_cache(monkeypatch, tmp_path):
    _fake_ytdlp(monkeypatch)
    response = MagicMock(
        content=b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello cache\n",
        encoding="utf-8",
        headers={},
    )
    response.raise_for_status.return_value = None
    monkeypatch.setattr("omnireach.media.service.httpx.get", lambda *args, **kwargs: response)

    first = parse_media(
        "https://www.youtube.com/watch?v=abc",
        language="en",
        output_dir=tmp_path,
    )
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cache hit must skip yt-dlp")
        ),
    )
    monkeypatch.setattr(
        "omnireach.media.service.httpx.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cache hit must skip subtitle HTTP")
        ),
    )

    second = parse_media(
        "https://www.youtube.com/watch?v=abc",
        language="en",
        output_dir=tmp_path,
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.cache_key == first.cache_key
    assert [artifact.path for artifact in second.artifacts] == [
        artifact.path for artifact in first.artifacts
    ]


def test_quick_parse_rejects_tampered_cache(monkeypatch, tmp_path):
    _fake_ytdlp(monkeypatch)
    calls = {"subtitle": 0}

    def subtitle_response(*args, **kwargs):
        calls["subtitle"] += 1
        response = MagicMock(
            content=b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nUntampered\n",
            encoding="utf-8",
            headers={},
        )
        response.raise_for_status.return_value = None
        return response

    monkeypatch.setattr("omnireach.media.service.httpx.get", subtitle_response)
    first = parse_media(
        "https://www.youtube.com/watch?v=abc",
        language="en",
        output_dir=tmp_path,
    )
    subtitle_path = Path(next(
        artifact.path for artifact in first.artifacts if artifact.kind == "subtitle"
    ))
    subtitle_path.write_text("tampered")

    second = parse_media(
        "https://www.youtube.com/watch?v=abc",
        language="en",
        output_dir=tmp_path,
    )

    assert second.cache_hit is False
    assert calls["subtitle"] == 2
    assert subtitle_path.read_bytes().startswith(b"WEBVTT")


def test_quick_parse_rejects_media_over_duration_limit(monkeypatch, tmp_path):
    _fake_ytdlp(monkeypatch)

    envelope = parse_media(
        "https://www.youtube.com/watch?v=abc",
        max_duration=10,
        output_dir=tmp_path,
    )

    assert envelope.ok is False
    assert envelope.errors[0].category == "limit"
    assert "213" in envelope.errors[0].message
    assert envelope.artifacts == []


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
    assert "subtitles require login" in envelope.warnings[0]


def _write_media_preference(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'[media]\ncookies_from_browser = "{value}"\n')


def _capturing_ytdlp(monkeypatch, commands, payload=None):
    monkeypatch.setattr("shutil.which", lambda tool: f"/usr/bin/{tool}")

    def fake_run(command, **kwargs):
        commands.append(command)
        if command == ["yt-dlp", "--version"]:
            return MagicMock(returncode=0, stdout="2026.06.09\n", stderr="")
        return MagicMock(
            returncode=0,
            stdout=json.dumps(payload if payload is not None else YTDLP_PAYLOAD),
            stderr="",
        )

    monkeypatch.setattr("subprocess.run", fake_run)


def test_media_cookies_preference_supplies_the_default_ytdlp_argv(
    monkeypatch, isolated_preferences
):
    _write_media_preference(isolated_preferences, "chrome:Profile 1")
    commands = []
    _capturing_ytdlp(monkeypatch, commands)

    envelope = inspect_media("https://www.youtube.com/watch?v=abc")

    inspect_command = next(c for c in commands if "--dump-single-json" in c)
    assert inspect_command[-3:-1] == ["--cookies-from-browser", "chrome:Profile 1"]
    assert envelope.ok is True
    assert "chrome:Profile 1" not in envelope.model_dump_json()


def test_explicit_cookies_argument_overrides_the_preference(
    monkeypatch, isolated_preferences
):
    _write_media_preference(isolated_preferences, "chrome:Profile 1")
    commands = []
    _capturing_ytdlp(monkeypatch, commands)

    inspect_media(
        "https://www.youtube.com/watch?v=abc",
        cookies_from_browser="firefox",
    )

    inspect_command = next(c for c in commands if "--dump-single-json" in c)
    assert inspect_command[-3:-1] == ["--cookies-from-browser", "firefox"]


def test_blank_cookies_preference_adds_no_flag(monkeypatch, isolated_preferences):
    _write_media_preference(isolated_preferences, "   ")
    commands = []
    _capturing_ytdlp(monkeypatch, commands)

    inspect_media("https://www.youtube.com/watch?v=abc")

    inspect_command = next(c for c in commands if "--dump-single-json" in c)
    assert "--cookies-from-browser" not in inspect_command


def test_cookies_preference_does_not_move_bilibili_off_the_api_backend(
    monkeypatch, isolated_preferences
):
    """Only an explicit argument may cost Bilibili its richer native backend."""
    _write_media_preference(isolated_preferences, "chrome:Profile 1")
    monkeypatch.setattr("shutil.which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(
        "subprocess.run",
        lambda command, **kwargs: (_ for _ in ()).throw(
            AssertionError("yt-dlp must not run for a cookie-free Bilibili inspect")
        ),
    )
    monkeypatch.setattr(
        "omnireach.media.service._inspect_bilibili",
        lambda url, timeout: (
            MediaEnvelope(
                ok=True, url=url, source="bilibili", media_type="video",
                backend="bilibili-api", mode="inspect", parsed_at="2026-09-03T00:00:00Z",
            ),
            [],
        ),
    )

    envelope = inspect_media("https://www.bilibili.com/video/BV1R1e4zKEh1")

    assert envelope.backend == "bilibili-api"


def test_download_uses_the_cookies_preference_and_keys_the_cache_on_it(
    monkeypatch, tmp_path, isolated_preferences
):
    _write_media_preference(isolated_preferences, "chrome:Profile 1")
    commands = []
    monkeypatch.setattr(
        "omnireach.media.service._yt_dlp_version", lambda timeout: "2026.06.09",
    )
    monkeypatch.setattr("shutil.which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(
        "subprocess.run",
        lambda command, **kwargs: MagicMock(
            returncode=0, stdout=json.dumps(DOUYIN_YTDLP_PAYLOAD), stderr="",
        ),
    )

    def fake_download(command, timeout):
        commands.append(command)
        template = Path(command[command.index("--output") + 1])
        path = Path(str(template).replace("%(ext)s", "mp4"))
        path.write_bytes(b"downloaded")
        return path.resolve()

    monkeypatch.setattr("omnireach.media.service._run_download", fake_download)

    url = "https://www.douyin.com/video/7664188112177079482"
    first = download_media(url, output_dir=tmp_path, max_bytes=20 * 1024 * 1024)
    assert commands[0][-3:-1] == ["--cookies-from-browser", "chrome:Profile 1"]

    _write_media_preference(isolated_preferences, "chrome:Profile 2")
    second = download_media(url, output_dir=tmp_path, max_bytes=20 * 1024 * 1024)

    assert first.cache_key != second.cache_key
    assert second.cache_hit is False
    assert len(commands) == 2


def _flaky_ytdlp(monkeypatch, failures, payload=None):
    """yt-dlp that answers the Douyin verification challenge `failures` times."""
    calls = {"n": 0}
    monkeypatch.setattr("shutil.which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr("omnireach.media.service.time.sleep", lambda seconds: None)

    def fake_run(command, **kwargs):
        if command == ["yt-dlp", "--version"]:
            return MagicMock(returncode=0, stdout="2026.06.09\n", stderr="")
        calls["n"] += 1
        if calls["n"] <= failures:
            return MagicMock(
                returncode=1,
                stdout="",
                stderr=(
                    "ERROR: [Douyin] 7658178405476748584: Fresh cookies "
                    "(not necessarily logged in) are needed"
                ),
            )
        return MagicMock(
            returncode=0,
            stdout=json.dumps(payload if payload is not None else DOUYIN_YTDLP_PAYLOAD),
            stderr="",
        )

    monkeypatch.setattr("subprocess.run", fake_run)
    return calls


def test_transient_fresh_cookies_challenge_is_retried_and_reported(monkeypatch):
    calls = _flaky_ytdlp(monkeypatch, failures=1)

    envelope = inspect_media("https://www.douyin.com/video/7658178405476748584")

    assert envelope.ok is True
    assert calls["n"] == 2
    assert any("succeeded on attempt 2" in warning for warning in envelope.warnings)


def test_fresh_cookies_challenge_gives_up_after_the_configured_attempts(monkeypatch):
    calls = _flaky_ytdlp(monkeypatch, failures=99)

    envelope = inspect_media("https://www.douyin.com/video/7658178405476748584")

    assert envelope.ok is False
    assert calls["n"] == _RETRY_ATTEMPTS
    assert envelope.errors[0].category == "blocked"
    assert envelope.errors[0].retryable is True
    assert f"verification challenge {_RETRY_ATTEMPTS} times" in envelope.errors[0].hint


def test_non_transient_failure_is_not_retried(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr("shutil.which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr("omnireach.media.service.time.sleep", lambda seconds: None)

    def fake_run(command, **kwargs):
        calls["n"] += 1
        return MagicMock(
            returncode=1, stdout="", stderr="ERROR: Video unavailable",
        )

    monkeypatch.setattr("subprocess.run", fake_run)

    envelope = inspect_media("https://www.douyin.com/video/7658178405476748584")

    assert envelope.ok is False
    assert calls["n"] == 1
    assert envelope.errors[0].retryable is False


def test_retry_never_outlives_the_caller_timeout_budget(monkeypatch):
    """Every attempt draws from one shared deadline, so retries cannot stretch it."""
    seen_timeouts = []
    clock = {"now": 0.0}
    monkeypatch.setattr("shutil.which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(
        "omnireach.media.service.time.monotonic", lambda: clock["now"],
    )

    def fake_sleep(seconds):
        clock["now"] += seconds

    monkeypatch.setattr("omnireach.media.service.time.sleep", fake_sleep)

    def fake_run(command, **kwargs):
        seen_timeouts.append(kwargs["timeout"])
        clock["now"] += 1.0
        return MagicMock(
            returncode=1, stdout="", stderr="ERROR: Fresh cookies are needed",
        )

    monkeypatch.setattr("subprocess.run", fake_run)

    envelope = inspect_media(
        "https://www.douyin.com/video/7658178405476748584", timeout=20,
    )

    assert envelope.ok is False
    # Attempts and backoffs are all charged to one deadline, so every attempt
    # after the first is handed strictly less than the caller's timeout and the
    # total never reaches it.
    assert seen_timeouts == [20.0, 18.0, 15.0, 11.0]
    assert clock["now"] == 10.0


def test_retry_is_skipped_when_too_little_budget_remains(monkeypatch):
    """A sliver-sized retry would report its own timeout, hiding the real cause."""
    seen_timeouts = []
    clock = {"now": 0.0}
    monkeypatch.setattr("shutil.which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(
        "omnireach.media.service.time.monotonic", lambda: clock["now"],
    )
    monkeypatch.setattr(
        "omnireach.media.service.time.sleep",
        lambda seconds: clock.__setitem__("now", clock["now"] + seconds),
    )

    def fake_run(command, **kwargs):
        seen_timeouts.append(kwargs["timeout"])
        clock["now"] += 1.0
        return MagicMock(
            returncode=1, stdout="", stderr="ERROR: Fresh cookies are needed",
        )

    monkeypatch.setattr("subprocess.run", fake_run)

    envelope = inspect_media(
        "https://www.douyin.com/video/7658178405476748584", timeout=3,
    )

    assert seen_timeouts == [3.0]
    assert "Fresh cookies" in envelope.errors[0].message
    assert envelope.errors[0].category == "blocked"


def test_download_retries_a_transient_challenge(monkeypatch, tmp_path):
    attempts = {"n": 0}
    monkeypatch.setattr("omnireach.media.service.time.sleep", lambda seconds: None)
    monkeypatch.setattr(
        "omnireach.media.service._ytdlp_payload",
        lambda *args, **kwargs: DOUYIN_YTDLP_PAYLOAD,
    )
    monkeypatch.setattr(
        "omnireach.media.service._yt_dlp_version", lambda timeout: "2026.06.09",
    )

    def fake_download(command, timeout):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("ERROR: [Douyin] 1: Fresh cookies are needed")
        template = Path(command[command.index("--output") + 1])
        path = Path(str(template).replace("%(ext)s", "mp4"))
        path.write_bytes(b"downloaded-after-retry")
        return path.resolve()

    monkeypatch.setattr("omnireach.media.service._run_download", fake_download)

    envelope = download_media(
        "https://www.douyin.com/video/7664188112177079482",
        output_dir=tmp_path,
        max_bytes=20 * 1024 * 1024,
    )

    assert envelope.ok is True
    assert attempts["n"] == 2
    assert any("yt-dlp download succeeded on attempt 2" in w for w in envelope.warnings)
