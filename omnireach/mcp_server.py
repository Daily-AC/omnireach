"""Dependency-free MCP tool server core for omnireach."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, TextIO
from urllib.parse import urlparse

from datetime import datetime, timezone

from omnireach import __version__
from omnireach.author import (
    AUTHOR_SOURCES,
    MAX_AUTHOR_LIMIT,
    author_catalog,
    failed_author_envelope,
)
from omnireach.contract import (
    AuthorEnvelope,
    FetchEnvelope,
    SearchEnvelope,
    SourceError,
)
from omnireach.fetcher import fetch
from omnireach.media.contract import MediaEnvelope, MediaError
from omnireach.media.service import download_media, inspect_media, parse_media
from omnireach.service import search

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "omnireach", "version": __version__}
TOOL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

TOOLS = [
    {
        "name": "omnireach_search",
        "title": "Search the web with omnireach",
        "description": (
            "Search the web and supported vertical platforms. Login-backed "
            "sources may read the user's Chrome session through a hidden "
            "ephemeral tab. Prefer this over browser automation for research."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                },
                "mode": {
                    "type": "string",
                    "enum": ["auto", "quick", "deep"],
                    "default": "auto",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                },
                "timeout": {
                    "type": "number",
                    "minimum": 1,
                    "maximum": 120,
                },
                "profile": {
                    "type": "string",
                    "minLength": 1,
                    "description": "OpenCLI Browser Bridge profile name or id",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "outputSchema": SearchEnvelope.model_json_schema(),
        "annotations": TOOL_ANNOTATIONS,
    },
    {
        "name": "omnireach_author",
        "title": "List a creator's own works with omnireach",
        "description": (
            "List the works one creator published, which keyword search cannot "
            "answer: searching a creator's name returns other accounts' fan "
            "edits and reaction videos. Accepts a nickname or a profile URL; a "
            "nickname is resolved by follower count, so pass the URL to pin an "
            "exact account. order=likes must page the entire catalog before it "
            "can rank, so it is slower and needs a larger timeout."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Creator nickname or profile URL",
                },
                "source": {
                    "type": "string",
                    "enum": list(AUTHOR_SOURCES),
                    "default": "douyin",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_AUTHOR_LIMIT,
                    "default": 20,
                },
                "order": {
                    "type": "string",
                    "enum": ["recent", "likes"],
                    "default": "recent",
                },
                "include_media_urls": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "Attach the expiring CDN playback URL to each result's "
                        "raw payload. Off by default: the URLs are signed, "
                        "short-lived, and large."
                    ),
                },
                "timeout": {
                    "type": "number",
                    "minimum": 5,
                    "maximum": 600,
                    "default": 180,
                },
            },
            "required": ["handle"],
            "additionalProperties": False,
        },
        "outputSchema": AuthorEnvelope.model_json_schema(),
        "annotations": TOOL_ANNOTATIONS,
    },
    {
        "name": "omnireach_fetch",
        "title": "Fetch a page with omnireach",
        "description": (
            "Read an HTTP(S) URL as Markdown. Ordinary pages avoid Chrome; "
            "supported login-walled pages may use a hidden ephemeral Chrome tab."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "format": "uri"},
                "backend": {
                    "type": "string",
                    "enum": ["auto", "http", "jina", "crwl", "opencli"],
                    "default": "auto",
                },
                "timeout": {
                    "type": "number",
                    "minimum": 1,
                    "maximum": 120,
                    "default": 30,
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        "outputSchema": FetchEnvelope.model_json_schema(),
        "annotations": TOOL_ANNOTATIONS,
    },
    {
        "name": "omnireach_parse_media",
        "title": "Inspect or parse media with omnireach",
        "description": (
            "Inspect YouTube, Bilibili, or direct media metadata. Quick mode "
            "also materializes available captions as bounded agent-friendly "
            "transcript artifacts without downloading the full video."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "format": "uri"},
                "mode": {
                    "type": "string",
                    "enum": ["inspect", "quick"],
                    "default": "quick",
                },
                "backend": {
                    "type": "string",
                    "enum": ["auto", "direct", "yt-dlp", "bilibili-api"],
                    "default": "auto",
                },
                "language": {"type": "string", "minLength": 1},
                "subtitle_url": {"type": "string", "format": "uri"},
                "cookies_from_browser": {
                    "type": "string",
                    "minLength": 1,
                    "description": (
                        "Explicit yt-dlp browser cookie source, e.g. chrome:Profile 1. "
                        "Omit to avoid reading browser cookies."
                    ),
                },
                "reuse_cache": {
                    "type": "boolean",
                    "default": True,
                },
                "max_duration": {
                    "type": "number",
                    "minimum": 1,
                    "maximum": 86400,
                    "description": "Reject media longer than this many seconds",
                },
                "timeout": {
                    "type": "number",
                    "minimum": 1,
                    "maximum": 300,
                    "default": 60,
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        "outputSchema": MediaEnvelope.model_json_schema(),
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    },
    {
        "name": "omnireach_download_media",
        "title": "Download a bounded Douyin video with omnireach",
        "description": (
            "Download one Douyin video through yt-dlp into an OmniReach-managed "
            "directory. The result contains a verified media artifact path, byte "
            "count, and SHA-256. Fresh browser cookies are usually required."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "format": "uri"},
                "quality": {
                    "type": "string",
                    "enum": ["compatible", "best", "small"],
                    "default": "compatible",
                },
                "cookies_from_browser": {
                    "type": "string",
                    "minLength": 1,
                    "description": (
                        "Explicit yt-dlp browser cookie source, e.g. chrome:Profile 1. "
                        "Omit to avoid reading browser cookies."
                    ),
                },
                "reuse_cache": {"type": "boolean", "default": True},
                "max_size_mb": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5120,
                    "default": 500,
                },
                "timeout": {
                    "type": "number",
                    "minimum": 1,
                    "maximum": 3600,
                    "default": 600,
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        "outputSchema": MediaEnvelope.model_json_schema(),
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    },
]


class InvalidParams(ValueError):
    """Raised when a tools/call argument object violates its schema."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _crashed_search(query: str, exc: Exception) -> dict[str, Any]:
    return SearchEnvelope(
        query=query,
        ts=_now(),
        errors=[SourceError(source="omnireach", error=str(exc), category="failed")],
    ).model_dump(mode="json")


def _crashed_fetch(url: str, exc: Exception) -> dict[str, Any]:
    return FetchEnvelope(
        url=url, fetched_at=_now(), errors=[str(exc)],
    ).model_dump(mode="json")


def _crashed_media(
    url: str,
    mode: str,
    exc: Exception,
) -> dict[str, Any]:
    return MediaEnvelope(
        ok=False,
        url=url,
        source="direct",
        media_type="unknown",
        mode=mode,
        parsed_at=_now(),
        errors=[MediaError(
            stage="resolve",
            backend="none",
            category="failed",
            message=f"{exc.__class__.__name__}: {exc}",
            hint="This is an omnireach bug; please report it with the message above",
        )],
    ).model_dump(mode="json")


def _result(request_id: object, value: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": value}


def _error(
    request_id: object,
    code: int,
    message: str,
) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _tool_result(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": payload,
        "isError": is_error,
    }


def _arguments(params: object) -> tuple[str, dict[str, Any]]:
    if not isinstance(params, dict):
        raise InvalidParams("params must be an object")
    name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(name, str) or not name:
        raise InvalidParams("tool name must be a non-empty string")
    if not isinstance(arguments, dict):
        raise InvalidParams("arguments must be an object")
    return name, arguments


def _reject_extra(arguments: dict[str, Any], allowed: set[str]) -> None:
    extra = sorted(set(arguments) - allowed)
    if extra:
        raise InvalidParams(f"unknown argument: {', '.join(extra)}")


def _number(
    arguments: dict[str, Any],
    name: str,
    default: float,
    *,
    integer: bool = False,
) -> float | int:
    value = arguments.get(name, default)
    expected = int if integer else (int, float)
    if isinstance(value, bool) or not isinstance(value, expected):
        kind = "an integer" if integer else "a number"
        raise InvalidParams(f"{name} must be {kind}")
    if not 1 <= value <= (50 if name == "limit" else 120):
        maximum = 50 if name == "limit" else 120
        raise InvalidParams(f"{name} must be between 1 and {maximum}")
    return value


def _validate_search(arguments: dict[str, Any]) -> dict[str, Any]:
    _reject_extra(
        arguments, {"query", "sources", "mode", "limit", "timeout", "profile"}
    )
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        raise InvalidParams("query must be a non-empty string")
    sources = arguments.get("sources")
    if sources is not None:
        if (
            not isinstance(sources, list)
            or not sources
            or any(not isinstance(source, str) or not source.strip() for source in sources)
        ):
            raise InvalidParams("sources must be a non-empty array of strings")
    mode = arguments.get("mode", "auto")
    if mode not in {"auto", "quick", "deep"}:
        raise InvalidParams("mode must be auto, quick, or deep")
    profile = arguments.get("profile")
    if profile is not None and (
        not isinstance(profile, str) or not profile.strip()
    ):
        raise InvalidParams("profile must be a non-empty string")
    validated = {
        "query": query,
        "sources": sources,
        "mode": mode,
        "limit": _number(arguments, "limit", 10, integer=True),
        "profile": profile,
    }
    if "timeout" in arguments:
        validated["timeout"] = _number(arguments, "timeout", 30)
    return validated


def _validate_author(arguments: dict[str, Any]) -> dict[str, Any]:
    _reject_extra(
        arguments,
        {"handle", "source", "limit", "order", "include_media_urls", "timeout"},
    )
    handle = arguments.get("handle")
    if not isinstance(handle, str) or not handle.strip():
        raise InvalidParams("handle must be a non-empty string")
    source = arguments.get("source", "douyin")
    if source not in AUTHOR_SOURCES:
        raise InvalidParams(f"source must be one of: {', '.join(AUTHOR_SOURCES)}")
    order = arguments.get("order", "recent")
    if order not in {"recent", "likes"}:
        raise InvalidParams("order must be recent or likes")
    limit = arguments.get("limit", 20)
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= MAX_AUTHOR_LIMIT
    ):
        raise InvalidParams(f"limit must be an integer between 1 and {MAX_AUTHOR_LIMIT}")
    include_media_urls = arguments.get("include_media_urls", False)
    if not isinstance(include_media_urls, bool):
        raise InvalidParams("include_media_urls must be a boolean")
    timeout = arguments.get("timeout", 180)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not 5 <= timeout <= 600
    ):
        raise InvalidParams("timeout must be between 5 and 600")
    return {
        "handle": handle,
        "source": source,
        "limit": limit,
        "order": order,
        "include_media_urls": include_media_urls,
        "timeout": timeout,
    }


def _validate_fetch(arguments: dict[str, Any]) -> dict[str, Any]:
    _reject_extra(arguments, {"url", "backend", "timeout"})
    url = arguments.get("url")
    if not isinstance(url, str):
        raise InvalidParams("url must be an HTTP or HTTPS URL")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidParams("url must be an absolute HTTP or HTTPS URL")
    backend = arguments.get("backend", "auto")
    if backend not in {"auto", "http", "jina", "crwl", "opencli"}:
        raise InvalidParams("unknown fetch backend")
    return {
        "url": url,
        "backend": backend,
        "timeout": _number(arguments, "timeout", 30),
    }


def _validate_media(arguments: dict[str, Any]) -> dict[str, Any]:
    _reject_extra(
        arguments,
        {
            "url", "mode", "backend", "language", "subtitle_url",
            "cookies_from_browser", "reuse_cache", "max_duration", "timeout",
        },
    )
    url = arguments.get("url")
    if not isinstance(url, str):
        raise InvalidParams("url must be an HTTP or HTTPS URL")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidParams("url must be an absolute HTTP or HTTPS URL")
    mode = arguments.get("mode", "quick")
    if mode not in {"inspect", "quick"}:
        raise InvalidParams("mode must be inspect or quick")
    backend = arguments.get("backend", "auto")
    if backend not in {"auto", "direct", "yt-dlp", "bilibili-api"}:
        raise InvalidParams("unknown media backend")
    language = arguments.get("language")
    if language is not None and (not isinstance(language, str) or not language.strip()):
        raise InvalidParams("language must be a non-empty string")
    subtitle_url = arguments.get("subtitle_url")
    if subtitle_url is not None:
        if not isinstance(subtitle_url, str):
            raise InvalidParams("subtitle_url must be an HTTP or HTTPS URL")
        subtitle_parsed = urlparse(subtitle_url)
        if subtitle_parsed.scheme not in {"http", "https"} or not subtitle_parsed.netloc:
            raise InvalidParams("subtitle_url must be an absolute HTTP or HTTPS URL")
    cookies_from_browser = arguments.get("cookies_from_browser")
    if cookies_from_browser is not None and (
        not isinstance(cookies_from_browser, str) or not cookies_from_browser.strip()
    ):
        raise InvalidParams("cookies_from_browser must be a non-empty string")
    reuse_cache = arguments.get("reuse_cache", True)
    if not isinstance(reuse_cache, bool):
        raise InvalidParams("reuse_cache must be a boolean")
    max_duration = arguments.get("max_duration")
    if max_duration is not None and (
        isinstance(max_duration, bool)
        or not isinstance(max_duration, (int, float))
        or not 1 <= max_duration <= 86400
    ):
        raise InvalidParams("max_duration must be between 1 and 86400")
    timeout = arguments.get("timeout", 60)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not 1 <= timeout <= 300
    ):
        raise InvalidParams("timeout must be between 1 and 300")
    return {
        "url": url,
        "mode": mode,
        "backend": backend,
        "language": language,
        "subtitle_url": subtitle_url,
        "cookies_from_browser": cookies_from_browser,
        "reuse_cache": reuse_cache,
        "max_duration": max_duration,
        "timeout": timeout,
    }


def _validate_media_download(arguments: dict[str, Any]) -> dict[str, Any]:
    _reject_extra(
        arguments,
        {
            "url", "quality", "cookies_from_browser", "reuse_cache",
            "max_size_mb", "timeout",
        },
    )
    url = arguments.get("url")
    if not isinstance(url, str):
        raise InvalidParams("url must be an HTTP or HTTPS URL")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidParams("url must be an absolute HTTP or HTTPS URL")
    quality = arguments.get("quality", "compatible")
    if quality not in {"compatible", "best", "small"}:
        raise InvalidParams("quality must be compatible, best, or small")
    cookies_from_browser = arguments.get("cookies_from_browser")
    if cookies_from_browser is not None and (
        not isinstance(cookies_from_browser, str) or not cookies_from_browser.strip()
    ):
        raise InvalidParams("cookies_from_browser must be a non-empty string")
    reuse_cache = arguments.get("reuse_cache", True)
    if not isinstance(reuse_cache, bool):
        raise InvalidParams("reuse_cache must be a boolean")
    max_size_mb = arguments.get("max_size_mb", 500)
    if (
        isinstance(max_size_mb, bool)
        or not isinstance(max_size_mb, int)
        or not 1 <= max_size_mb <= 5120
    ):
        raise InvalidParams("max_size_mb must be an integer between 1 and 5120")
    timeout = arguments.get("timeout", 600)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not 1 <= timeout <= 3600
    ):
        raise InvalidParams("timeout must be between 1 and 3600")
    return {
        "url": url,
        "quality": quality,
        "cookies_from_browser": cookies_from_browser,
        "reuse_cache": reuse_cache,
        "max_bytes": max_size_mb * 1024 * 1024,
        "timeout": timeout,
    }


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "omnireach_search":
        kwargs = _validate_search(arguments)
        query = kwargs.pop("query")
        try:
            envelope = asyncio.run(search(query, **kwargs))
        except ValueError as exc:
            raise InvalidParams(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            return _tool_result(_crashed_search(query, exc), is_error=True)
        return _tool_result(envelope.model_dump(mode="json"))
    if name == "omnireach_author":
        kwargs = _validate_author(arguments)
        handle = kwargs.pop("handle")
        try:
            envelope = asyncio.run(author_catalog(handle, **kwargs))
        except ValueError as exc:
            raise InvalidParams(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            return _tool_result(
                failed_author_envelope(
                    handle, kwargs["source"], str(exc),
                ).model_dump(mode="json"),
                is_error=True,
            )
        return _tool_result(
            envelope.model_dump(mode="json"), is_error=bool(envelope.errors),
        )
    if name == "omnireach_fetch":
        kwargs = _validate_fetch(arguments)
        url = kwargs.pop("url")
        try:
            envelope = fetch(url, **kwargs)
        except Exception as exc:  # noqa: BLE001
            return _tool_result(_crashed_fetch(url, exc), is_error=True)
        return _tool_result(
            envelope.model_dump(mode="json"),
            is_error=not bool(envelope.content_markdown),
        )
    if name == "omnireach_parse_media":
        kwargs = _validate_media(arguments)
        url = kwargs.pop("url")
        mode = kwargs.pop("mode")
        try:
            if mode == "inspect":
                kwargs.pop("language")
                kwargs.pop("subtitle_url")
                kwargs.pop("reuse_cache")
                kwargs.pop("max_duration")
                envelope = inspect_media(url, **kwargs)
            else:
                envelope = parse_media(
                    url,
                    mode="quick",
                    **kwargs,
                )
        except Exception as exc:  # noqa: BLE001
            return _tool_result(_crashed_media(url, mode, exc), is_error=True)
        return _tool_result(
            envelope.model_dump(mode="json"), is_error=not envelope.ok,
        )
    if name == "omnireach_download_media":
        kwargs = _validate_media_download(arguments)
        url = kwargs.pop("url")
        try:
            envelope = download_media(url, **kwargs)
        except Exception as exc:  # noqa: BLE001
            return _tool_result(_crashed_media(url, "download", exc), is_error=True)
        return _tool_result(
            envelope.model_dump(mode="json"), is_error=not envelope.ok,
        )
    raise KeyError(name)


def handle_message(message: object) -> dict[str, Any] | None:
    """Handle one decoded JSON-RPC message."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        request_id = message.get("id") if isinstance(message, dict) else None
        return _error(request_id, -32600, "Invalid Request")
    request_id = message.get("id")
    method = message.get("method")
    if not isinstance(method, str):
        return _error(request_id, -32600, "Invalid Request")
    if method.startswith("notifications/"):
        return None
    if method == "initialize":
        return _result(request_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": (
                "Use omnireach_search for research, omnireach_author when the "
                "question is what one creator posted, omnireach_fetch for reading "
                "pages, omnireach_parse_media for media metadata or transcripts, "
                "and omnireach_download_media for bounded Douyin downloads before "
                "launching browser automation."
            ),
        })
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        try:
            name, arguments = _arguments(message.get("params"))
            value = _call_tool(name, arguments)
        except InvalidParams as exc:
            return _error(request_id, -32602, str(exc))
        except KeyError:
            return _error(request_id, -32601, "Tool not found")
        return _result(request_id, value)
    return _error(request_id, -32601, "Method not found")


def serve_stdio(
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> None:
    """Serve newline-delimited MCP JSON-RPC until stdin closes."""
    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    error_stream = stderr or sys.stderr
    for line in input_stream:
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _error(None, -32700, f"Parse error: {exc.msg}")
        else:
            try:
                response = handle_message(message)
            except Exception as exc:  # noqa: BLE001
                print(f"omnireach MCP internal error: {exc}", file=error_stream)
                request_id = message.get("id") if isinstance(message, dict) else None
                response = _error(request_id, -32603, "Internal error")
        if response is None:
            continue
        output_stream.write(
            json.dumps(response, ensure_ascii=False, separators=(",", ":"))
        )
        output_stream.write("\n")
        output_stream.flush()
