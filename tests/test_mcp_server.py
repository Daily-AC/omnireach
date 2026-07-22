import json

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


def test_tools_list_exposes_search_fetch_and_media():
    response = handle_message({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    })

    tools = {tool["name"]: tool for tool in response["result"]["tools"]}
    assert set(tools) == {
        "omnireach_search", "omnireach_fetch", "omnireach_parse_media",
    }
    assert tools["omnireach_search"]["inputSchema"]["required"] == ["query"]
    assert tools["omnireach_fetch"]["annotations"]["readOnlyHint"] is True
    assert tools["omnireach_parse_media"]["annotations"]["readOnlyHint"] is False
    assert tools["omnireach_parse_media"]["outputSchema"]["title"] == "MediaEnvelope"


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
