import json
import select
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


class _ArticleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = (
            b"<html><head><title>MCP process article</title></head>"
            b"<body><main><h1>MCP process article</h1>"
            b"<p>Fetched through the real stdio process.</p></main></body></html>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


@pytest.fixture
def article_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ArticleHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/article"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _send(proc, message):
    proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def _read(proc):
    line = proc.stdout.readline()
    assert line, f"MCP process exited early: {proc.stderr.read()}"
    return json.loads(line)


def test_mcp_stdio_lifecycle_and_fetch(article_url):
    proc = subprocess.Popen(
        [sys.executable, "-m", "omnireach", "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        _send(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1"},
            },
        })
        initialized = _read(proc)
        assert initialized["result"]["protocolVersion"] == "2025-06-18"

        _send(proc, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })
        readable, _, _ = select.select([proc.stdout], [], [], 0.1)
        assert readable == []

        _send(proc, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })
        listed = _read(proc)
        assert {tool["name"] for tool in listed["result"]["tools"]} == {
            "omnireach_search",
            "omnireach_fetch",
        }

        _send(proc, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "omnireach_fetch",
                "arguments": {"url": article_url, "backend": "http"},
            },
        })
        called = _read(proc)
        result = called["result"]
        assert result["isError"] is False
        assert result["structuredContent"]["backend"] == "http"
        assert "MCP process article" in result["structuredContent"]["content_markdown"]
    finally:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        try:
            returncode = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            raise
    assert returncode == 0, proc.stderr.read()
