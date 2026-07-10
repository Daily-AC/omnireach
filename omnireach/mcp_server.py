"""Dependency-free MCP tool server core for omnireach."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlparse

from omnireach import __version__
from omnireach.contract import FetchEnvelope, SearchEnvelope
from omnireach.fetcher import fetch
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
                    "default": 30,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "outputSchema": SearchEnvelope.model_json_schema(),
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
]


class InvalidParams(ValueError):
    """Raised when a tools/call argument object violates its schema."""


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
    _reject_extra(arguments, {"query", "sources", "mode", "limit", "timeout"})
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
    return {
        "query": query,
        "sources": sources,
        "mode": mode,
        "limit": _number(arguments, "limit", 10, integer=True),
        "timeout": _number(arguments, "timeout", 30),
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


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "omnireach_search":
        kwargs = _validate_search(arguments)
        query = kwargs.pop("query")
        try:
            envelope = asyncio.run(search(query, **kwargs))
        except ValueError as exc:
            raise InvalidParams(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            return _tool_result({"error": str(exc)}, is_error=True)
        return _tool_result(envelope.model_dump(mode="json"))
    if name == "omnireach_fetch":
        kwargs = _validate_fetch(arguments)
        url = kwargs.pop("url")
        try:
            envelope = fetch(url, **kwargs)
        except Exception as exc:  # noqa: BLE001
            return _tool_result({"error": str(exc)}, is_error=True)
        return _tool_result(
            envelope.model_dump(mode="json"),
            is_error=not bool(envelope.content_markdown),
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
                "Use omnireach_search for research and omnireach_fetch for reading "
                "URLs before launching browser automation."
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
