"""Media backend selection, normalization, and artifact materialization."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypeVar
from urllib.parse import parse_qsl, urlparse

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
from omnireach.preferences import load_preferences

_DIRECT_EXTENSIONS = {
    ".aac", ".flac", ".m4a", ".m4v", ".mkv", ".mov", ".mp3", ".mp4",
    ".ogg", ".opus", ".wav", ".webm",
}
_SUBTITLE_FORMAT_PREFERENCE = ("vtt", "json3", "srt", "json")
_PREVIEW_LIMIT = 5000
_PUBLIC_TRACK_LIMIT = 40
_SUBTITLE_MAX_BYTES = 20 * 1024 * 1024
_DEFAULT_DOWNLOAD_MAX_BYTES = 500 * 1024 * 1024
_BVID_RE = re.compile(r"(?:^|/)(BV[0-9A-Za-z]+)(?:[/?#]|$)")
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36"
    ),
}
_RETRY_ATTEMPTS = 4
_RETRY_BACKOFF_SECONDS = (1.0, 2.0, 3.0)
# A retry that only has a sliver of the budget left would die of a timeout and
# report *that* instead of the upstream failure it was retrying, so below this
# much remaining budget the original error is surfaced untouched.
_RETRY_MIN_SLICE_SECONDS = 5.0
# Douyin answers `aweme/v1/web/aweme/detail/` with a device-verification
# challenge instead of the payload every so often; yt-dlp surfaces that as
# "Fresh cookies (not necessarily logged in) are needed". Measured 2026-09-03
# against one video with an identical command line: 1 failure in 10 runs when
# the endpoint was cold, 4 in 10 once it had been queried a few dozen times,
# and the outcome looked independent per attempt at both 1s and 5s spacing —
# so attempts buy reliability while longer backoff does not. Four attempts put
# the residual failure rate near 4% at the worst observed rate. The structural
# fix is calling the same API from a real page context, where it is never
# challenged; see issue #46.
_RETRYABLE_BACKEND_MARKERS = (
    "fresh cookies",
    "temporarily unavailable",
    "connection reset",
    "connection aborted",
    "remote end closed connection",
    "read timed out",
    "http error 429",
    "http error 500",
    "http error 502",
    "http error 503",
    "http error 504",
)

_T = TypeVar("_T")


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
    if (
        host == "douyin.com"
        or host.endswith(".douyin.com")
        or host == "iesdouyin.com"
        or host.endswith(".iesdouyin.com")
    ):
        return "douyin"
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


def _safe_public_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = urlparse(value)
    sensitive = {
        "auth", "expire", "expires", "key-pair-id", "policy", "sig",
        "signature", "token", "x-expires", "x-signature",
    }
    if any(key.casefold() in sensitive for key, _ in parse_qsl(parsed.query)):
        return None
    return value


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


def _effective_cookies(cookies_from_browser: str | None) -> str | None:
    """Explicit argument wins; otherwise fall back to `[media].cookies_from_browser`.

    Resolved once per public entry point so the value that reaches yt-dlp is
    also the value that goes into the cache key. Backend routing keeps using
    the *explicit* argument, so setting the preference never silently moves
    Bilibili off the richer bilibili-api path.
    """
    if cookies_from_browser and cookies_from_browser.strip():
        return cookies_from_browser
    value = load_preferences().media.cookies_from_browser
    return value.strip() if value and value.strip() else None


def _is_retryable_backend_error(message: str) -> bool:
    folded = message.casefold()
    return any(marker in folded for marker in _RETRYABLE_BACKEND_MARKERS)


def _run_retrying(
    operation: Callable[[float], _T],
    *,
    timeout: float,
    label: str,
    warnings: list[str] | None = None,
    attempts: int = _RETRY_ATTEMPTS,
) -> _T:
    """Run one bounded backend call, retrying only known-transient failures.

    Every attempt draws from the caller's single timeout budget, so retrying
    can never stretch the wall clock beyond what the caller asked for. A
    non-transient failure is re-raised on the first attempt, untouched.
    """
    attempts = max(1, attempts)
    deadline = time.monotonic() + timeout
    last: RuntimeError | None = None
    for attempt in range(attempts):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or (attempt and remaining < _RETRY_MIN_SLICE_SECONDS):
            break
        try:
            result = operation(remaining)
        except RuntimeError as exc:
            if not _is_retryable_backend_error(str(exc)):
                raise
            last = exc
            backoff = _RETRY_BACKOFF_SECONDS[
                min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)
            ]
            if attempt + 1 >= attempts or deadline - time.monotonic() <= backoff:
                break
            time.sleep(backoff)
            continue
        if attempt and warnings is not None:
            warnings.append(
                f"{label} succeeded on attempt {attempt + 1} after a "
                "transient upstream failure"
            )
        return result
    if last is not None:
        raise last
    raise RuntimeError(f"{label} had no time budget left to run")


def _ytdlp_payload(
    url: str,
    timeout: float,
    cookies_from_browser: str | None = None,
    *,
    retry_warnings: list[str] | None = None,
) -> dict[str, Any]:
    if not shutil.which("yt-dlp"):
        raise FileNotFoundError("yt-dlp is not installed")
    command = ["yt-dlp", "--dump-single-json", "--skip-download", "--no-warnings"]
    if _source(url) == "bilibili":
        command.extend(["--write-subs", "--sub-langs", "all"])
    if cookies_from_browser:
        command.extend(["--cookies-from-browser", cookies_from_browser])
    command.append(url)
    return _run_retrying(
        lambda remaining: _run_json(command, remaining),
        timeout=timeout,
        label="yt-dlp metadata",
        warnings=retry_warnings,
    )


def _normalize_ytdlp(
    url: str,
    payload: dict[str, Any],
    timeout: float,
) -> tuple[MediaEnvelope, list[dict[str, str]]]:
    tracks, internal_tracks, omitted_tracks = _subtitle_tracks(payload)
    duration = payload.get("duration")
    media_type: Literal["video", "audio", "unknown"] = "unknown"
    if payload.get("vcodec") not in {None, "none"} or payload.get("width"):
        media_type = "video"
    elif payload.get("acodec") not in {None, "none"}:
        media_type = "audio"
    thumbnail_url = _safe_public_url(payload.get("thumbnail"))
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
            thumbnail_url=thumbnail_url,
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
    if payload.get("thumbnail") and thumbnail_url is None:
        envelope.warnings.append(
            "Signed thumbnail URL omitted from public metadata"
        )
    return envelope, internal_tracks


def _inspect_ytdlp(
    url: str,
    timeout: float,
    cookies_from_browser: str | None = None,
) -> tuple[MediaEnvelope, list[dict[str, str]]]:
    retry_warnings: list[str] = []
    payload = _ytdlp_payload(
        url, timeout, cookies_from_browser, retry_warnings=retry_warnings,
    )
    envelope, internal_tracks = _normalize_ytdlp(url, payload, timeout)
    envelope.warnings.extend(retry_warnings)
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


def _failed_envelope(
    url: str,
    mode: Literal["inspect", "quick", "download"],
    backend: str,
    exc: Exception,
) -> MediaEnvelope:
    unavailable = isinstance(exc, FileNotFoundError)
    invalid = isinstance(exc, ValueError)
    limited = isinstance(exc, OverflowError)
    folded = str(exc).casefold()
    blocked = any(marker in folded for marker in (
        "http error 401", "http error 403", "http error 412", "captcha",
        "verification", "fresh cookies", "login required", "sign in",
    ))
    retryable = (
        isinstance(exc, subprocess.TimeoutExpired)
        or _is_retryable_backend_error(folded)
        or any(marker in folded for marker in ("ssl", "eof", "connection"))
    )
    hint = ""
    if unavailable and "yt-dlp" in str(exc):
        hint = "Install yt-dlp and retry: pip install -U yt-dlp"
    elif unavailable and "ffprobe" in str(exc):
        hint = "Install ffmpeg (which includes ffprobe) and retry"
    elif isinstance(exc, subprocess.TimeoutExpired):
        hint = "Retry with a larger --timeout value"
    elif "fresh cookies" in folded:
        hint = (
            f"The upstream answered a verification challenge {_RETRY_ATTEMPTS} times "
            "in a row; retry the same command, pass "
            "--cookies-from-browser 'chrome:Profile 1', or set "
            "[media].cookies_from_browser in ~/.omnireach/preferences.toml"
        )
    elif "cookie" in folded or "login required" in folded or "sign in" in folded:
        hint = (
            "Retry with an explicitly authorized browser profile, for example "
            "--cookies-from-browser 'chrome:Profile 1'"
        )
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
            category=(
                "unavailable" if unavailable
                else "blocked" if blocked
                else "limit" if limited
                else "invalid" if invalid
                else "failed"
            ),
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
        return _inspect_ytdlp(url, timeout, _effective_cookies(cookies_from_browser))
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


def _file_artifact(path: Path, kind: str, mime: str) -> MediaArtifact:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return MediaArtifact(
        kind=kind,
        path=str(path.resolve()),
        mime=mime,
        bytes=size,
        sha256=digest.hexdigest(),
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


def _download_cache_key(
    url: str,
    quality: str,
    cookies_from_browser: str | None,
    max_bytes: int,
) -> str:
    payload = json.dumps({
        "operation": "download",
        "url": url,
        "quality": quality,
        "cookies_from_browser": cookies_from_browser,
        "max_bytes": max_bytes,
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _download_artifact_dir(
    url: str,
    output_dir: Path | None,
    cache_key: str,
) -> Path:
    base = (
        output_dir.expanduser()
        if output_dir is not None
        else Path.home() / ".cache" / "omnireach" / "media" / "downloads"
    )
    url_key = hashlib.sha256(url.encode()).hexdigest()[:16]
    root = base / f"douyin-{url_key}-{cache_key[:12]}"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _download_formats(payload: dict[str, Any]) -> list[dict[str, Any]]:
    formats = payload.get("formats")
    if not isinstance(formats, list):
        return []
    return [
        item for item in formats
        if isinstance(item, dict)
        and item.get("format_id")
        and str(item.get("ext") or "").lower() == "mp4"
        and item.get("vcodec") not in {None, "none"}
        and item.get("acodec") not in {None, "none"}
    ]


def _format_bytes(item: dict[str, Any]) -> int | None:
    value = item.get("filesize") or item.get("filesize_approx")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return round(value)
    return None


def _select_download_format(
    payload: dict[str, Any],
    quality: Literal["compatible", "best", "small"],
    max_bytes: int,
) -> dict[str, Any]:
    formats = _download_formats(payload)
    bounded = [item for item in formats if _format_bytes(item) is not None]
    eligible = [item for item in bounded if (_format_bytes(item) or 0) <= max_bytes]
    if not eligible:
        if bounded:
            smallest = min(_format_bytes(item) or 0 for item in bounded)
            raise OverflowError(
                f"smallest downloadable MP4 is {smallest} bytes, above the "
                f"{max_bytes} byte limit"
            )
        raise RuntimeError(
            "Douyin did not report a bounded combined MP4 format; refusing an "
            "unbounded download"
        )

    def score(item: dict[str, Any]) -> tuple[int, float, int]:
        pixels = int(item.get("width") or 0) * int(item.get("height") or 0)
        bitrate = float(item.get("tbr") or 0)
        return pixels, bitrate, _format_bytes(item) or 0

    if quality == "small":
        return min(eligible, key=lambda item: (_format_bytes(item) or 0, *score(item)))
    if quality == "compatible":
        h264 = [
            item for item in eligible
            if str(item.get("vcodec") or "").casefold().startswith(("h264", "avc"))
        ]
        return max(h264 or eligible, key=score)
    return max(eligible, key=score)


def _run_download(command: list[str], timeout: float) -> Path:
    proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()
        raise RuntimeError(detail[-1000:])
    paths = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not paths:
        raise RuntimeError("yt-dlp completed without reporting the downloaded file")
    return Path(paths[-1]).expanduser().resolve()


def download_media(
    url: str,
    *,
    quality: Literal["compatible", "best", "small"] = "compatible",
    cookies_from_browser: str | None = None,
    output_dir: Path | None = None,
    reuse_cache: bool = True,
    max_bytes: int = _DEFAULT_DOWNLOAD_MAX_BYTES,
    timeout: float = 600,
) -> MediaEnvelope:
    """Download one bounded Douyin MP4 and return a verified local artifact."""
    try:
        _validate_url(url)
    except ValueError as exc:
        return _failed_envelope(url, "download", "yt-dlp", exc)
    if _source(url) != "douyin":
        return MediaEnvelope(
            ok=False,
            url=url,
            source=_source(url),
            media_type="unknown",
            backend="yt-dlp",
            mode="download",
            parsed_at=_now(),
            errors=[MediaError(
                stage="resolve",
                backend="yt-dlp",
                category="invalid",
                message="media download currently supports Douyin URLs only",
            )],
        )
    if quality not in {"compatible", "best", "small"}:
        return _failed_envelope(
            url, "download", "yt-dlp", ValueError("unknown download quality")
        )
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        return _failed_envelope(
            url, "download", "yt-dlp", ValueError("max_bytes must be a positive integer")
        )
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout < 1:
        return _failed_envelope(
            url, "download", "yt-dlp", ValueError("timeout must be a positive number")
        )

    effective_cookies = _effective_cookies(cookies_from_browser)
    cache_key = _download_cache_key(
        url, quality, effective_cookies, max_bytes,
    )
    retry_warnings: list[str] = []
    try:
        root = _download_artifact_dir(url, output_dir, cache_key)
    except OSError as exc:
        failed = _failed_envelope(url, "download", "yt-dlp", exc)
        failed.errors[0].stage = "artifact"
        return failed
    if reuse_cache:
        cached = _load_cached_envelope(root, url, cache_key)
        if cached is not None and cached.mode == "download":
            return cached

    try:
        payload = _ytdlp_payload(
            url,
            min(timeout, 120),
            effective_cookies,
            retry_warnings=retry_warnings,
        )
        envelope, _ = _normalize_ytdlp(url, payload, min(timeout, 10))
        selected = _select_download_format(payload, quality, max_bytes)
        extension = str(selected.get("ext") or "mp4").lower()
        expected_path = (root / f"video.{extension}").resolve()
        for stale in root.glob("video.*"):
            if stale.is_file():
                stale.unlink()
        command = [
            "yt-dlp", "--no-playlist", "--no-warnings", "--no-progress",
            "--format", str(selected["format_id"]),
            "--max-filesize", str(max_bytes),
            "--output", str(root / "video.%(ext)s"),
            "--print", "after_move:filepath",
        ]
        if effective_cookies:
            command.extend(["--cookies-from-browser", effective_cookies])
        command.append(url)
        downloaded_path = _run_retrying(
            lambda remaining: _run_download(command, remaining),
            timeout=timeout,
            label="yt-dlp download",
            warnings=retry_warnings,
        )
        if not downloaded_path.is_relative_to(root) or downloaded_path != expected_path:
            raise RuntimeError("yt-dlp reported a file outside the managed download path")
        if not downloaded_path.is_file():
            raise RuntimeError("yt-dlp reported a downloaded file that does not exist")
        actual_bytes = downloaded_path.stat().st_size
        if actual_bytes > max_bytes:
            downloaded_path.unlink(missing_ok=True)
            raise OverflowError(
                f"downloaded file is {actual_bytes} bytes, above the {max_bytes} byte limit"
            )
    except (
        FileNotFoundError,
        RuntimeError,
        subprocess.TimeoutExpired,
        OSError,
        ValueError,
        OverflowError,
    ) as exc:
        for partial in root.glob("video.*"):
            if partial.is_file():
                try:
                    partial.unlink(missing_ok=True)
                except OSError:
                    pass
        failed = _failed_envelope(url, "download", "yt-dlp", exc)
        failed.warnings.extend(retry_warnings)
        failed.errors[0].stage = "download"
        if isinstance(exc, OverflowError):
            failed.errors[0].category = "limit"
            failed.errors[0].hint = "Retry with a larger --max-size-mb value"
        return failed

    envelope.mode = "download"
    envelope.cache_key = cache_key
    envelope.warnings.extend(retry_warnings)
    if envelope.metadata is not None:
        envelope.metadata.width = selected.get("width")
        envelope.metadata.height = selected.get("height")
        envelope.metadata.codec = str(selected.get("vcodec") or "") or None
    mime = mimetypes.guess_type(downloaded_path.name)[0] or "video/mp4"
    envelope.artifacts.append(_file_artifact(downloaded_path, "media", mime))
    envelope.warnings.append(
        f"Downloaded yt-dlp format {selected['format_id']} ({quality})"
    )
    manifest_payload = envelope.model_dump(mode="json")
    manifest_bytes = json.dumps(
        manifest_payload, ensure_ascii=False, indent=2,
    ).encode()
    envelope.artifacts.append(_write_artifact(
        root / "manifest.json", manifest_bytes, "manifest", "application/json",
    ))
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
        _effective_cookies(cookies_from_browser),
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
