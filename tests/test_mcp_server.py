import json

import pytest

from omnireach.mcp_server import handle_message


def test_initialize_advertises_static_tools():
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"},
        },
    })

    assert response["id"] == 1
    assert response["result"]["protocolVersion"] == "2025-06-18"
    assert response["result"]["capabilities"] == {
        "tools": {"listChanged": False}
    }


def test_tools_list_exposes_search_fetch_parse_and_download_media():
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    })

    tools = {tool["name"]: tool for tool in response["result"]["tools"]}
    assert set(tools) == {
        "omnireach_search", "omnireach_author",
        "omnireach_fetch", "omnireach_parse_media",
        "omnireach_download_media",
    }
    assert tools["omnireach_search"]["inputSchema"]["required"] == ["query"]
    assert tools["omnireach_fetch"]["annotations"]["readOnlyHint"] is True
    assert tools["omnireach_parse_media"]["annotations"]["readOnlyHint"] is False
    assert tools["omnireach_parse_media"]["outputSchema"]["title"] == "MediaEnvelope"
    assert tools["omnireach_download_media"]["annotations"]["readOnlyHint"] is False


def test_download_media_tool_uses_managed_output_and_converts_size(monkeypatch):
    from omnireach.media.contract import MediaEnvelope

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

    monkeypatch.setattr("omnireach.mcp_server.download_media", fake_download)
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 15,
        "method": "tools/call",
        "params": {
            "name": "omnireach_download_media",
            "arguments": {
                "url": "https://www.douyin.com/video/123",
                "quality": "small",
                "cookies_from_browser": "chrome:Profile 1",
                "max_size_mb": 25,
                "timeout": 90,
            },
        },
    })

    assert response["result"]["isError"] is False
    assert captured == {
        "url": "https://www.douyin.com/video/123",
        "quality": "small",
        "cookies_from_browser": "chrome:Profile 1",
        "reuse_cache": True,
        "max_bytes": 25 * 1024 * 1024,
        "timeout": 90,
    }


def test_download_media_tool_rejects_output_directory_and_invalid_limit():
    output_dir = handle_message({
        "jsonrpc": "2.0",
        "id": 16,
        "method": "tools/call",
        "params": {
            "name": "omnireach_download_media",
            "arguments": {
                "url": "https://www.douyin.com/video/123",
                "output_dir": "/tmp/arbitrary",
            },
        },
    })
    invalid_limit = handle_message({
        "jsonrpc": "2.0",
        "id": 17,
        "method": "tools/call",
        "params": {
            "name": "omnireach_download_media",
            "arguments": {
                "url": "https://www.douyin.com/video/123",
                "max_size_mb": 0,
            },
        },
    })

    assert output_dir["error"]["code"] == -32602
    assert invalid_limit["error"]["code"] == -32602


def test_initialized_notification_has_no_response():
    assert handle_message({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }) is None


def test_ping_returns_empty_result():
    response = handle_message({
        "jsonrpc": "2.0", "id": 8, "method": "ping"
    })
    assert response == {"jsonrpc": "2.0", "id": 8, "result": {}}


def test_search_tool_returns_structured_and_text_content(monkeypatch):
    async def fake_search(query, **kwargs):
        from omnireach.contract import SearchEnvelope

        return SearchEnvelope(query=query, ts="2026-07-10T00:00:00Z")

    monkeypatch.setattr("omnireach.mcp_server.search", fake_search)
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "omnireach_search",
            "arguments": {"query": "q"},
        },
    })

    result = response["result"]
    assert result["structuredContent"]["query"] == "q"
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    assert result["isError"] is False


def test_search_tool_omits_timeout_by_default_and_passes_profile(monkeypatch):
    captured = {}

    async def fake_search(query, **kwargs):
        from omnireach.contract import SearchEnvelope

        captured.update(kwargs)
        return SearchEnvelope(query=query, ts="2026-07-15T00:00:00Z")

    monkeypatch.setattr("omnireach.mcp_server.search", fake_search)
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {
            "name": "omnireach_search",
            "arguments": {"query": "q", "profile": "934ve3jn"},
        },
    })

    assert "error" not in response
    assert "timeout" not in captured
    assert captured["profile"] == "934ve3jn"


def test_fetch_exhaustion_is_a_tool_error(monkeypatch):
    from omnireach.contract import FetchEnvelope

    monkeypatch.setattr(
        "omnireach.mcp_server.fetch",
        lambda url, **kwargs: FetchEnvelope(
            url=url,
            fetched_at="2026-07-10T00:00:00Z",
            errors=["http: blocked"],
        ),
    )
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "omnireach_fetch",
            "arguments": {"url": "https://example.com"},
        },
    })

    assert response["result"]["isError"] is True
    assert response["result"]["structuredContent"]["errors"] == [
        "http: blocked"
    ]


def test_media_inspect_tool_does_not_materialize_artifacts(monkeypatch):
    from omnireach.media.contract import MediaEnvelope

    captured = {}

    def fake_inspect(url, **kwargs):
        captured.update(kwargs)
        return MediaEnvelope(
            ok=True,
            url=url,
            source="youtube",
            media_type="video",
            backend="yt-dlp",
            mode="inspect",
            parsed_at="2026-07-22T00:00:00Z",
        )

    monkeypatch.setattr("omnireach.mcp_server.inspect_media", fake_inspect)
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "omnireach_parse_media",
            "arguments": {
                "url": "https://www.youtube.com/watch?v=abc",
                "mode": "inspect",
                "backend": "yt-dlp",
                "cookies_from_browser": "chrome:Profile 1",
            },
        },
    })

    assert response["result"]["isError"] is False
    assert response["result"]["structuredContent"]["artifacts"] == []
    assert captured == {
        "backend": "yt-dlp",
        "cookies_from_browser": "chrome:Profile 1",
        "timeout": 60,
    }


def test_media_tool_rejects_non_http_subtitle_url():
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {
            "name": "omnireach_parse_media",
            "arguments": {
                "url": "https://example.com/video.mp4",
                "subtitle_url": "file:///tmp/subtitle.vtt",
            },
        },
    })

    assert response["error"]["code"] == -32602


def test_media_tool_rejects_arbitrary_output_directory():
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {
            "name": "omnireach_parse_media",
            "arguments": {
                "url": "https://example.com/video.mp4",
                "output_dir": "/tmp/arbitrary",
            },
        },
    })

    assert response["error"]["code"] == -32602


def test_media_tool_rejects_invalid_cache_and_duration_options():
    invalid_cache = handle_message({
        "jsonrpc": "2.0",
        "id": 13,
        "method": "tools/call",
        "params": {
            "name": "omnireach_parse_media",
            "arguments": {
                "url": "https://example.com/video.mp4",
                "reuse_cache": "yes",
            },
        },
    })
    invalid_duration = handle_message({
        "jsonrpc": "2.0",
        "id": 14,
        "method": "tools/call",
        "params": {
            "name": "omnireach_parse_media",
            "arguments": {
                "url": "https://example.com/video.mp4",
                "max_duration": 0,
            },
        },
    })

    assert invalid_cache["error"]["code"] == -32602
    assert invalid_duration["error"]["code"] == -32602


def test_invalid_tool_arguments_return_minus_32602():
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "omnireach_fetch",
            "arguments": {"url": "file:///tmp/x"},
        },
    })

    assert response["error"]["code"] == -32602


def test_unknown_tool_and_method_return_minus_32601():
    unknown_tool = handle_message({
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {"name": "missing", "arguments": {}},
    })
    unknown_method = handle_message({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "missing/method",
    })

    assert unknown_tool["error"]["code"] == -32601
    assert unknown_method["error"]["code"] == -32601


def _call(name, arguments, request_id=900):
    return handle_message({
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })


def _author_call(arguments, request_id=800):
    return _call("omnireach_author", arguments, request_id)


def test_crashing_search_still_answers_with_a_valid_envelope(monkeypatch):
    """An `isError` payload the declared outputSchema rejects is a silent failure."""
    from omnireach.contract import SearchEnvelope

    def boom(*args, **kwargs):
        raise RuntimeError("synthetic adapter crash")

    monkeypatch.setattr("omnireach.mcp_server.search", boom)

    result = _call("omnireach_search", {"query": "python"})["result"]
    payload = result["structuredContent"]

    assert result["isError"] is True
    assert SearchEnvelope.model_validate(payload).errors[0].error.endswith(
        "synthetic adapter crash"
    )


def test_crashing_fetch_still_answers_with_a_valid_envelope(monkeypatch):
    from omnireach.contract import FetchEnvelope

    monkeypatch.setattr(
        "omnireach.mcp_server.fetch",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic crash")),
    )

    result = _call("omnireach_fetch", {"url": "https://example.com/a"})["result"]

    assert result["isError"] is True
    envelope = FetchEnvelope.model_validate(result["structuredContent"])
    assert envelope.url == "https://example.com/a"
    assert envelope.errors == ["synthetic crash"]


def test_crashing_media_download_still_answers_with_a_valid_envelope(monkeypatch):
    from omnireach.media.contract import MediaEnvelope

    monkeypatch.setattr(
        "omnireach.mcp_server.download_media",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic crash")),
    )

    result = _call(
        "omnireach_download_media",
        {"url": "https://www.douyin.com/video/1"},
    )["result"]

    assert result["isError"] is True
    envelope = MediaEnvelope.model_validate(result["structuredContent"])
    assert envelope.ok is False
    assert envelope.mode == "download"
    assert len(envelope.errors) == 1
    assert "synthetic crash" in envelope.errors[0].message


def test_author_tool_declares_the_catalog_envelope_schema():
    response = handle_message({
        "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {},
    })

    tool = next(
        item for item in response["result"]["tools"]
        if item["name"] == "omnireach_author"
    )
    assert tool["inputSchema"]["required"] == ["handle"]
    assert tool["inputSchema"]["properties"]["order"]["enum"] == ["recent", "likes"]
    assert tool["inputSchema"]["properties"]["include_media_urls"]["default"] is False
    assert "author" in tool["outputSchema"]["properties"]


def test_author_tool_forwards_validated_arguments(monkeypatch):
    from omnireach.contract import AuthorEnvelope

    captured = {}

    async def fake_catalog(handle, **kwargs):
        captured.update({"handle": handle, **kwargs})
        return AuthorEnvelope(query=handle, ts="2026-09-03T00:00:00Z", scanned=355)

    monkeypatch.setattr("omnireach.mcp_server.author_catalog", fake_catalog)

    result = _author_call({
        "handle": "彭十六", "limit": 50, "order": "likes", "timeout": 300,
    })["result"]

    assert result["isError"] is False
    assert result["structuredContent"]["scanned"] == 355
    assert captured == {
        "handle": "彭十六",
        "source": "douyin",
        "limit": 50,
        "order": "likes",
        "include_media_urls": False,
        "timeout": 300,
    }


def test_author_tool_answers_a_crash_with_a_valid_envelope(monkeypatch):
    from omnireach.contract import AuthorEnvelope

    async def boom(handle, **kwargs):
        raise RuntimeError("synthetic bridge crash")

    monkeypatch.setattr("omnireach.mcp_server.author_catalog", boom)

    result = _author_call({"handle": "彭十六"})["result"]

    assert result["isError"] is True
    envelope = AuthorEnvelope.model_validate(result["structuredContent"])
    assert envelope.errors[0].error == "synthetic bridge crash"


def test_author_tool_reports_a_structured_failure_as_an_error(monkeypatch):
    from omnireach.contract import AuthorEnvelope, SourceError

    async def unavailable(handle, **kwargs):
        return AuthorEnvelope(
            query=handle,
            ts="2026-09-03T00:00:00Z",
            errors=[SourceError(
                source="douyin", error="reload the extension", category="unavailable",
            )],
        )

    monkeypatch.setattr("omnireach.mcp_server.author_catalog", unavailable)

    assert _author_call({"handle": "彭十六"})["result"]["isError"] is True


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({}, "handle must be"),
        ({"handle": "  "}, "handle must be"),
        ({"handle": "x", "source": "youtube"}, "source must be"),
        ({"handle": "x", "limit": 0}, "limit must be"),
        ({"handle": "x", "limit": 201}, "limit must be"),
        ({"handle": "x", "order": "oldest"}, "order must be"),
        ({"handle": "x", "include_media_urls": "yes"}, "include_media_urls must be"),
        ({"handle": "x", "timeout": 1}, "timeout must be"),
        ({"handle": "x", "nope": 1}, "unknown argument"),
    ],
)
def test_author_tool_rejects_invalid_arguments(arguments, message):
    response = _author_call(arguments)

    assert response["error"]["code"] == -32602
    assert message in response["error"]["message"]
