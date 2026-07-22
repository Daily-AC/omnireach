"""Media backend selection, normalization, and artifact materialization."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from omnireach.media.contract import (
    MediaArtifact,
    MediaEnvelope,
    MediaError,
    MediaMetadata,
    MediaProvenance,
    MediaTrack,
    MediaTranscript,
    TranscriptSegment,
)
from omnireach.media.subtitles import (
    parse_subtitle,
    subtitle_format_from_url,
    transcript_markdown,
    transcript_text,
)

_DIRECT_EXTENSIONS = {
    ".aac", ".flac", ".m4a", ".m4v", ".mkv", ".mov", ".mp3", ".mp4",
    ".ogg", ".opus", ".wav", ".webm",
}
_SUBTITLE_FORMAT_PREFERENCE = ("vtt", "json3", "srt", "json")
_PREVIEW_LIMIT = 5000
_PUBLIC_TRACK_LIMIT = 40
_SUBTITLE_MAX_BYTES = 20 * 1024 * 1024
_BVID_RE = re.compile(r"(?:^|/)(BV[0-9A-Za-z]+)(?:[/?#]|$)")
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36"
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _source(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if (
        host == "youtu.be"
        or host == "youtube.com"
        or host.endswith(".youtube.com")
        or host == "youtube-nocookie.com"
        or host.endswith(".youtube-nocookie.com")
    ):
        return "youtube"
    if host == "bilibili.com" or host.endswith(".bilibili.com") or host == "b23.tv":
        return "bilibili"
    return "direct"


def _is_direct_url(url: str) -> bool:
    return Path(urlparse(url).path).suffix.lower() in _DIRECT_EXTENSIONS


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an absolute HTTP or HTTPS URL")


def _run_json(command: list[str], timeout: float) -> dict[str, Any]:
    proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()
        raise RuntimeError(detail[-1000:])
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("backend returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("backend returned a non-object JSON payload")
    return payload


def _yt_dlp_version(timeout: float) -> str | None:
    try:
        proc = subprocess.run(
            ["yt-dlp", "--version"], capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _published_at(value: Any) -> str | None:
    if not value:
        return None
    raw = str(value)
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    if raw.isdigit() and len(raw) >= 9:
        return datetime.fromtimestamp(
            int(raw), timezone.utc,
        ).isoformat().replace("+00:00", "Z")
    return raw


def _subtitle_tracks(
    payload: dict[str, Any],
) -> tuple[list[MediaTrack], list[dict[str, str]], int]:
    tracks_by_key: dict[tuple[str, str], MediaTrack] = {}
    internal: list[dict[str, str]] = []
    for field, source in (("subtitles", "publisher"), ("automatic_captions", "automatic")):
        languages = payload.get(field)
        if not isinstance(languages, dict):
            continue
        for language, formats in languages.items():
            if not isinstance(formats, list):
                continue
            seen: set[str] = set()
            for item in formats:
                if not isinstance(item, dict) or not (item.get("url") or item.get("data")):
                    continue
                extension = str(item.get("ext") or "vtt").lower()
                if extension in seen or extension not in _SUBTITLE_FORMAT_PREFERENCE:
                    continue
                seen.add(extension)
                internal_track = {
                    "language": str(language),
                    "format": extension,
                    "source": source,
                }
                if item.get("url"):
                    internal_track["url"] = str(item["url"])
                else:
                    internal_track["data"] = str(item["data"])
                internal.append(internal_track)
                key = (str(language), source)
                current = tracks_by_key.get(key)
                if (
                    current is None
                    or _SUBTITLE_FORMAT_PREFERENCE.index(extension)
                    < _SUBTITLE_FORMAT_PREFERENCE.index(current.format)
                ):
                    tracks_by_key[key] = MediaTrack(
                        language=str(language), format=extension, source=source,
                    )
    tracks = sorted(
        tracks_by_key.values(),
        key=lambda track: (
            0 if track.source == "publisher" else 1,
            track.language,
        ),
    )
    omitted = max(0, len(tracks) - _PUBLIC_TRACK_LIMIT)
    return tracks[:_PUBLIC_TRACK_LIMIT], internal, omitted


def _inspect_ytdlp(
    url: str,
    timeout: float,
    cookies_from_browser: str | None = None,
) -> tuple[MediaEnvelope, list[dict[str, str]]]:
    if not shutil.which("yt-dlp"):
        raise FileNotFoundError("yt-dlp is not installed")
    command = ["yt-dlp", "--dump-single-json", "--skip-download", "--no-warnings"]
    if _source(url) == "bilibili":
        command.extend(["--write-subs", "--sub-langs", "all"])
    if cookies_from_browser:
        command.extend(["--cookies-from-browser", cookies_from_browser])
    command.append(url)
    payload = _run_json(command, timeout)
    tracks, internal_tracks, omitted_tracks = _subtitle_tracks(payload)
    duration = payload.get("duration")
    media_type: Literal["video", "audio", "unknown"] = "unknown"
    if payload.get("vcodec") not in {None, "none"} or payload.get("width"):
        media_type = "video"
    elif payload.get("acodec") not in {None, "none"}:
        media_type = "audio"
    envelope = MediaEnvelope(
        ok=True,
        url=url,
        source=_source(url),
        media_type=media_type,
        backend="yt-dlp",
        mode="inspect",
        parsed_at=_now(),
        metadata=MediaMetadata(
            id=str(payload["id"]) if payload.get("id") is not None else None,
            title=payload.get("title"),
            author=payload.get("channel") or payload.get("uploader"),
            description=payload.get("description"),
            duration_ms=round(float(duration) * 1000) if duration is not None else None,
            published_at=_published_at(payload.get("upload_date") or payload.get("timestamp")),
            thumbnail_url=payload.get("thumbnail"),
            width=payload.get("width"),
            height=payload.get("height"),
            codec=payload.get("vcodec") or payload.get("acodec"),
        ),
        tracks=tracks,
        provenance=[MediaProvenance(
            tool="yt-dlp", tool_version=_yt_dlp_version(min(timeout, 10)), inspected_at=_now(),
        )],
    )
    if omitted_tracks:
        envelope.warnings.append(
            f"Subtitle track listing omitted {omitted_tracks} languages; "
            "request a language explicitly when parsing"
        )
    return envelope, internal_tracks


def _bilibili_bvid(url: str, timeout: float) -> str:
    match = _BVID_RE.search(urlparse(url).path)
    if match:
        return match.group(1)
    if (urlparse(url).hostname or "").lower() == "b23.tv":
        response = httpx.get(
            url, headers=_HTTP_HEADERS, follow_redirects=True, timeout=timeout,
        )
        response.raise_for_status()
        match = _BVID_RE.search(urlparse(str(response.url)).path)
        if match:
            return match.group(1)
    raise ValueError("Bilibili URL does not contain a BV id")


def _http_json(url: str, timeout: float, *, referer: str | None = None) -> dict[str, Any]:
    headers = dict(_HTTP_HEADERS)
    if referer:
        headers["Referer"] = referer
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("upstream returned a non-object JSON payload")
    if payload.get("code") not in {None, 0}:
        raise RuntimeError(
            f"Bilibili API {payload.get('code')}: {payload.get('message') or 'unknown error'}"
        )
    return payload


def _inspect_bilibili(url: str, timeout: float) -> tuple[MediaEnvelope, list[dict[str, str]]]:
    bvid = _bilibili_bvid(url, timeout)
    canonical_url = f"https://www.bilibili.com/video/{bvid}"
    view = _http_json(
        f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
        timeout,
        referer=canonical_url,
    ).get("data")
    if not isinstance(view, dict):
        raise RuntimeError("Bilibili view response omitted data")
    dimension = view.get("dimension") if isinstance(view.get("dimension"), dict) else {}
    owner = view.get("owner") if isinstance(view.get("owner"), dict) else {}
    tracks: list[MediaTrack] = []
    internal_tracks: list[dict[str, str]] = []
    warnings: list[str] = []
    cid = view.get("cid")
    if cid:
        try:
            player = _http_json(
                f"https://api.bilibili.com/x/player/wbi/v2?bvid={bvid}&cid={cid}",
                timeout,
                referer=canonical_url,
            ).get("data")
            if isinstance(player, dict) and player.get("need_login_subtitle"):
                warnings.append(
                    "Bilibili subtitles require login; retry with "
                    "--cookies-from-browser <browser[:profile]> "
                    "(for example, 'chrome:Profile 1')"
                )
            subtitle = player.get("subtitle") if isinstance(player, dict) else None
            subtitles = subtitle.get("subtitles") if isinstance(subtitle, dict) else None
            if isinstance(subtitles, list):
                for item in subtitles:
                    if not isinstance(item, dict) or not item.get("subtitle_url"):
                        continue
                    language = str(item.get("lan") or "und")
                    subtitle_url = str(item["subtitle_url"])
                    if subtitle_url.startswith("//"):
                        subtitle_url = "https:" + subtitle_url
                    tracks.append(MediaTrack(
                        language=language, format="json", source="publisher",
                    ))
                    internal_tracks.append({
                        "language": language,
                        "format": "json",
                        "source": "publisher",
                        "url": subtitle_url,
                    })
        except (httpx.HTTPError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            warnings.append(f"Bilibili subtitle discovery failed: {exc}")
    published_at = None
    if view.get("pubdate") is not None:
        published_at = datetime.fromtimestamp(
            int(view["pubdate"]), timezone.utc,
        ).isoformat().replace("+00:00", "Z")
    envelope = MediaEnvelope(
        ok=True,
        url=url,
        source="bilibili",
        media_type="video",
        backend="bilibili-api",
        mode="inspect",
        parsed_at=_now(),
        metadata=MediaMetadata(
            id=bvid,
            title=view.get("title"),
            author=owner.get("name"),
            description=view.get("desc"),
            duration_ms=int(view["duration"]) * 1000 if view.get("duration") is not None else None,
            published_at=published_at,
            thumbnail_url=(
                "https:" + view["pic"]
                if isinstance(view.get("pic"), str) and view["pic"].startswith("//")
                else str(view["pic"]).replace("http://", "https://", 1)
                if view.get("pic")
                else None
            ),
            width=dimension.get("width"),
            height=dimension.get("height"),
        ),
        tracks=tracks,
        warnings=warnings,
        provenance=[MediaProvenance(tool="bilibili-api", inspected_at=_now())],
    )
    return envelope, internal_tracks


def _inspect_direct(url: str, timeout: float) -> tuple[MediaEnvelope, list[dict[str, str]]]:
    if not shutil.which("ffprobe"):
        raise FileNotFoundError("ffprobe is not installed")
    payload = _run_json([
        "ffprobe", "-v", "error", "-show_format", "-show_streams",
        "-of", "json", url,
    ], timeout)
    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    fmt = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    tags = fmt.get("tags") if isinstance(fmt.get("tags"), dict) else {}
    duration = fmt.get("duration")
    media_type: Literal["video", "audio", "unknown"] = (
        "video" if video else "audio" if audio else "unknown"
    )
    primary = video or audio or {}
    envelope = MediaEnvelope(
        ok=True,
        url=url,
        source="direct",
        media_type=media_type,
        backend="direct",
        mode="inspect",
        parsed_at=_now(),
        metadata=MediaMetadata(
            id=hashlib.sha256(url.encode()).hexdigest()[:16],
            title=tags.get("title") or Path(urlparse(url).path).name or None,
            author=tags.get("artist") or tags.get("author"),
            duration_ms=round(float(duration) * 1000) if duration is not None else None,
            width=video.get("width") if video else None,
            height=video.get("height") if video else None,
            codec=primary.get("codec_name"),
        ),
        provenance=[MediaProvenance(tool="ffprobe", inspected_at=_now())],
    )
    return envelope, []


def _failed_envelope(url: str, mode: Literal["inspect", "quick"], backend: str, exc: Exception) -> MediaEnvelope:
    unavailable = isinstance(exc, FileNotFoundError)
    folded = str(exc).casefold()
    blocked = any(marker in folded for marker in (
        "http error 401", "http error 403", "http error 412", "captcha", "verification",
    ))
    retryable = isinstance(exc, subprocess.TimeoutExpired) or any(
        marker in folded for marker in ("ssl", "eof", "connection", "temporarily unavailable")
    )
    hint = ""
    if unavailable and "yt-dlp" in str(exc):
        hint = "Install yt-dlp and retry: pip install -U yt-dlp"
    elif unavailable and "ffprobe" in str(exc):
        hint = "Install ffmpeg (which includes ffprobe) and retry"
    elif isinstance(exc, subprocess.TimeoutExpired):
        hint = "Retry with a larger --timeout value"
    elif blocked:
        hint = "The upstream blocked anonymous access; retry on another network or with an authenticated backend"
    elif retryable:
        hint = "Transient network failure; retry the same command"
    return MediaEnvelope(
        ok=False,
        url=url,
        source=_source(url),
        media_type="unknown",
        backend=backend if backend in {"direct", "yt-dlp", "bilibili-api"} else None,
        mode=mode,
        parsed_at=_now(),
        errors=[MediaError(
            stage="inspect",
            backend=backend,
            category="unavailable" if unavailable else "blocked" if blocked else "failed",
            message=str(exc),
            hint=hint,
            retryable=retryable,
        )],
    )


def _inspect_with_tracks(
    url: str,
    *,
    backend: Literal["auto", "direct", "yt-dlp", "bilibili-api"] = "auto",
    cookies_from_browser: str | None = None,
    timeout: float = 60,
) -> tuple[MediaEnvelope, list[dict[str, str]]]:
    try:
        _validate_url(url)
    except ValueError as exc:
        return MediaEnvelope(
            ok=False, url=url, source="direct", media_type="unknown", mode="inspect",
            parsed_at=_now(), errors=[MediaError(
                stage="resolve", backend="none", category="invalid", message=str(exc),
            )],
        ), []
    selected = "direct" if backend == "auto" and _is_direct_url(url) else backend
    if selected == "auto":
        selected = (
            "bilibili-api"
            if _source(url) == "bilibili" and not cookies_from_browser
            else "yt-dlp"
        )
    try:
        if selected == "direct":
            return _inspect_direct(url, timeout)
        if selected == "bilibili-api":
            return _inspect_bilibili(url, timeout)
        return _inspect_ytdlp(url, timeout, cookies_from_browser)
    except (
        FileNotFoundError,
        RuntimeError,
        subprocess.TimeoutExpired,
        OSError,
        ValueError,
        httpx.HTTPError,
    ) as exc:
        return _failed_envelope(url, "inspect", selected, exc), []


def inspect_media(
    url: str,
    *,
    backend: Literal["auto", "direct", "yt-dlp", "bilibili-api"] = "auto",
    cookies_from_browser: str | None = None,
    timeout: float = 60,
) -> MediaEnvelope:
    envelope, _ = _inspect_with_tracks(
        url,
        backend=backend,
        cookies_from_browser=cookies_from_browser,
        timeout=timeout,
    )
    return envelope


def _choose_track(
    tracks: list[dict[str, str]], language: str | None,
) -> dict[str, str] | None:
    if not tracks:
        return None
    candidates = tracks
    if language:
        exact = [track for track in tracks if track["language"].casefold() == language.casefold()]
        prefix = [track for track in tracks if track["language"].casefold().startswith(language.casefold() + "-")]
        candidates = exact or prefix
        if not candidates:
            return None
    return min(candidates, key=lambda track: (
        0 if track["source"] == "publisher" else 1,
        _SUBTITLE_FORMAT_PREFERENCE.index(track["format"])
        if track["format"] in _SUBTITLE_FORMAT_PREFERENCE else 99,
        track["language"],
    ))


def _write_artifact(path: Path, content: bytes, kind: str, mime: str) -> MediaArtifact:
    path.write_bytes(content)
    return MediaArtifact(
        kind=kind, path=str(path.resolve()), mime=mime, bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )


def _parse_cache_key(
    url: str,
    backend: str,
    language: str | None,
    subtitle_url: str | None,
    cookies_from_browser: str | None,
    max_duration: float | None,
) -> str:
    payload = json.dumps({
        "url": url,
        "backend": backend,
        "language": language,
        "subtitle_url": subtitle_url,
        "cookies_from_browser": cookies_from_browser,
        "max_duration": max_duration,
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _artifact_dir(
    url: str,
    source: str,
    output_dir: Path | None,
    cache_key: str,
) -> Path:
    if output_dir is not None:
        root = output_dir.expanduser()
    else:
        key = hashlib.sha256(url.encode()).hexdigest()[:16]
        root = (
            Path.home() / ".cache" / "omnireach" / "media"
            / f"{source}-{key}" / cache_key[:16]
        )
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _load_cached_envelope(
    root: Path,
    url: str,
    cache_key: str,
) -> MediaEnvelope | None:
    manifest_path = root / "manifest.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        envelope = MediaEnvelope.model_validate_json(manifest_bytes)
    except (OSError, ValueError):
        return None
    if not envelope.ok or envelope.url != url or envelope.cache_key != cache_key:
        return None
    root = root.resolve()
    for artifact in envelope.artifacts:
        path = Path(artifact.path).resolve()
        if not path.is_relative_to(root) or path == manifest_path.resolve():
            return None
        try:
            content = path.read_bytes()
        except OSError:
            return None
        if len(content) != artifact.bytes:
            return None
        if hashlib.sha256(content).hexdigest() != artifact.sha256:
            return None
    envelope.artifacts.append(MediaArtifact(
        kind="manifest",
        path=str(manifest_path.resolve()),
        mime="application/json",
        bytes=len(manifest_bytes),
        sha256=hashlib.sha256(manifest_bytes).hexdigest(),
    ))
    envelope.cache_hit = True
    return envelope


def parse_media(
    url: str,
    *,
    mode: Literal["quick"] = "quick",
    backend: Literal["auto", "direct", "yt-dlp", "bilibili-api"] = "auto",
    language: str | None = None,
    subtitle_url: str | None = None,
    cookies_from_browser: str | None = None,
    output_dir: Path | None = None,
    reuse_cache: bool = True,
    max_duration: float | None = None,
    timeout: float = 60,
) -> MediaEnvelope:
    """Inspect media and materialize normalized metadata/transcript artifacts."""
    try:
        _validate_url(url)
    except ValueError:
        envelope, _ = _inspect_with_tracks(
            url,
            backend=backend,
            cookies_from_browser=cookies_from_browser,
            timeout=timeout,
        )
        envelope.mode = mode
        return envelope
    cache_key = _parse_cache_key(
        url,
        backend,
        language,
        subtitle_url,
        cookies_from_browser,
        max_duration,
    )
    root = _artifact_dir(url, _source(url), output_dir, cache_key)
    if reuse_cache:
        cached = _load_cached_envelope(root, url, cache_key)
        if cached is not None:
            return cached

    envelope, internal_tracks = _inspect_with_tracks(
        url,
        backend=backend,
        cookies_from_browser=cookies_from_browser,
        timeout=timeout,
    )
    envelope.mode = mode
    envelope.cache_key = cache_key
    if not envelope.ok:
        return envelope
    if (
        max_duration is not None
        and envelope.metadata is not None
        and envelope.metadata.duration_ms is not None
        and envelope.metadata.duration_ms > max_duration * 1000
    ):
        envelope.ok = False
        envelope.errors.append(MediaError(
            stage="resolve",
            backend=envelope.backend or "none",
            category="limit",
            message=(
                f"media duration {envelope.metadata.duration_ms / 1000:.3f}s "
                f"exceeds {max_duration:g}s limit"
            ),
            hint="Retry with a larger --max-duration value",
        ))
        return envelope
    metadata_payload = envelope.metadata.model_dump(mode="json") if envelope.metadata else {}
    metadata_bytes = json.dumps(metadata_payload, ensure_ascii=False, indent=2).encode()
    envelope.artifacts.append(_write_artifact(
        root / "metadata.json", metadata_bytes, "metadata", "application/json",
    ))

    selected: dict[str, str] | None
    if subtitle_url:
        try:
            _validate_url(subtitle_url)
        except ValueError as exc:
            envelope.ok = False
            envelope.errors.append(MediaError(
                stage="subtitle", backend=envelope.backend or "none", category="invalid",
                message=f"subtitle_url: {exc}",
            ))
            return envelope
        selected = {
            "language": language or "und",
            "format": subtitle_format_from_url(subtitle_url),
            "source": "sidecar",
            "url": subtitle_url,
        }
        envelope.tracks.append(MediaTrack(
            language=selected["language"], format=selected["format"], source="sidecar",
        ))
    else:
        selected = _choose_track(internal_tracks, language)

    segments: list[TranscriptSegment] = []
    if selected is None:
        message = "No supported subtitle track is available"
        if language:
            message += f" for language '{language}'"
        envelope.warnings.append(message)
    else:
        try:
            if "data" in selected:
                raw = selected["data"].encode()
                content = selected["data"]
            else:
                response = httpx.get(
                    selected["url"], timeout=timeout, follow_redirects=True,
                )
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > _SUBTITLE_MAX_BYTES:
                    raise OverflowError(
                        f"subtitle exceeds {_SUBTITLE_MAX_BYTES} byte limit"
                    )
                raw = response.content
                content = raw.decode(response.encoding or "utf-8", errors="replace")
            if len(raw) > _SUBTITLE_MAX_BYTES:
                raise OverflowError(
                    f"subtitle exceeds {_SUBTITLE_MAX_BYTES} byte limit"
                )
            segments = parse_subtitle(content, selected["format"])
            if not segments:
                raise ValueError("subtitle track contained no parseable cues")
            subtitle_name = f"subtitle.{selected['format']}"
            mime = mimetypes.guess_type(subtitle_name)[0] or "text/plain"
            envelope.artifacts.append(_write_artifact(
                root / subtitle_name, raw, "subtitle", mime,
            ))
        except (
            httpx.HTTPError,
            UnicodeError,
            ValueError,
            json.JSONDecodeError,
            OverflowError,
        ) as exc:
            envelope.ok = False
            category: Literal["failed", "blocked", "limit"] = "failed"
            hint = "Try another --language or provide --subtitle-url"
            retryable = False
            if isinstance(exc, OverflowError):
                category = "limit"
                hint = "Use a smaller subtitle track"
            elif isinstance(exc, httpx.HTTPStatusError):
                status = exc.response.status_code
                if status in {401, 403}:
                    category = "blocked"
                    hint = "The subtitle host rejected access; retry with an authorized source"
                elif status == 429:
                    category = "limit"
                    hint = "Subtitle host rate-limited the request; retry later"
                    retryable = True
                elif status >= 500:
                    hint = "Subtitle host failed temporarily; retry the same command"
                    retryable = True
            elif isinstance(exc, httpx.HTTPError):
                hint = "Transient subtitle download failure; retry the same command"
                retryable = True
            envelope.errors.append(MediaError(
                stage="subtitle",
                backend=envelope.backend or "none",
                category=category,
                message=str(exc),
                hint=hint,
                retryable=retryable,
            ))

    if segments and selected:
        transcript_json = json.dumps(
            [segment.model_dump(mode="json") for segment in segments],
            ensure_ascii=False, indent=2,
        ).encode()
        markdown = transcript_markdown(segments).encode()
        envelope.artifacts.extend([
            _write_artifact(root / "transcript.json", transcript_json, "transcript_json", "application/json"),
            _write_artifact(root / "transcript.md", markdown, "transcript_markdown", "text/markdown"),
        ])
        full_text = transcript_text(segments)
        envelope.transcript = MediaTranscript(
            language=selected["language"],
            source=selected["source"],
            segment_count=len(segments),
            text_preview=full_text[:_PREVIEW_LIMIT],
            truncated=len(full_text) > _PREVIEW_LIMIT,
        )

    manifest_payload = envelope.model_dump(mode="json")
    manifest_bytes = json.dumps(manifest_payload, ensure_ascii=False, indent=2).encode()
    envelope.artifacts.append(_write_artifact(
        root / "manifest.json", manifest_bytes, "manifest", "application/json",
    ))
    return envelope
