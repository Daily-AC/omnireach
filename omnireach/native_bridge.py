"""Dependency-free localhost protocol for the Omnireach Chrome extension."""

from __future__ import annotations

import hmac
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from omnireach.bridge_install import bridge_configured, bridge_paths

BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 19826
MAX_RESULT_BYTES = 4 * 1024 * 1024


class NativeBridgeUnavailable(Exception):
    """The native extension bridge is not installed, connected, or available."""


class NativeBridgeCommandError(RuntimeError):
    """The extension accepted a command but failed to execute its contract."""


@dataclass
class _BridgeState:
    token: str
    job: dict[str, Any]
    delivered: bool = False
    response: dict[str, Any] | None = None
    delivered_event: threading.Event = field(default_factory=threading.Event)
    result_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)


class _BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], state: _BridgeState) -> None:
        self.state = state
        super().__init__(address, _BridgeHandler)


class _BridgeHandler(BaseHTTPRequestHandler):
    server: _BridgeServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, status: int, payload: object | None = None) -> None:
        body = b"" if payload is None else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        if body:
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _authorized(self) -> bool:
        expected = f"Bearer {self.server.state.token}"
        supplied = self.headers.get("Authorization", "")
        if hmac.compare_digest(supplied, expected):
            return True
        self._send_json(401, {"error": "unauthorized"})
        return False

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(204)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/v1/job":
            self._send_json(404, {"error": "not found"})
            return
        if not self._authorized():
            return
        state = self.server.state
        with state.lock:
            if state.delivered:
                self._send_json(204)
                return
            state.delivered = True
            job = state.job
        self._send_json(200, job)
        state.delivered_event.set()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/result":
            self._send_json(404, {"error": "not found"})
            return
        if not self._authorized():
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "invalid content length"})
            return
        if length <= 0:
            self._send_json(400, {"error": "empty body"})
            return
        if length > MAX_RESULT_BYTES:
            self._send_json(413, {"error": "result too large"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "malformed JSON"})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "result must be an object"})
            return
        state = self.server.state
        if payload.get("id") != state.job["id"]:
            self._send_json(409, {"error": "result id mismatch"})
            return
        if not isinstance(payload.get("ok"), bool):
            self._send_json(400, {"error": "result ok must be boolean"})
            return
        with state.lock:
            if state.response is not None:
                self._send_json(409, {"error": "result already submitted"})
                return
            state.response = payload
        self._send_json(204)
        state.result_event.set()


def _wait_for(
    event: threading.Event,
    timeout: float,
    cancel_event: threading.Event | None,
) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        if cancel_event is not None and cancel_event.is_set():
            raise NativeBridgeUnavailable("native bridge command cancelled")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        if event.wait(min(0.05, remaining)):
            return True


def _validate_response(response: dict[str, Any] | None) -> list[dict[str, Any]]:
    if response is None:
        raise NativeBridgeCommandError("native bridge returned no result envelope")
    if response.get("ok") is True:
        items = response.get("items")
        if not isinstance(items, list) or any(
            not isinstance(item, dict) for item in items
        ):
            raise NativeBridgeCommandError(
                "native bridge returned an invalid items payload"
            )
        return items
    error = response.get("error")
    if not isinstance(error, dict):
        raise NativeBridgeCommandError("native bridge returned an invalid error payload")
    kind = error.get("kind")
    message = str(error.get("message") or "native bridge command failed")
    if kind == "auth":
        raise NativeBridgeUnavailable(message)
    raise NativeBridgeCommandError(message)


def run_native_job(
    command: str,
    payload: dict[str, object],
    *,
    home: Path | None = None,
    port: int = BRIDGE_PORT,
    connect_timeout: float = 2.0,
    result_timeout: float = 22.0,
    cancel_event: threading.Event | None = None,
) -> list[dict[str, Any]]:
    if cancel_event is not None and cancel_event.is_set():
        raise NativeBridgeUnavailable("native bridge command cancelled")
    if not bridge_configured(home=home):
        raise NativeBridgeUnavailable(
            "native bridge is not installed; run `omnireach bridge install`"
        )
    paths = bridge_paths(home=home)
    token = paths.token_path.read_text(encoding="utf-8").strip()
    if not token:
        raise NativeBridgeUnavailable("native bridge token is empty")
    state = _BridgeState(
        token=token,
        job={
            "id": uuid.uuid4().hex,
            "command": command,
            "payload": payload,
        },
    )
    try:
        server = _BridgeServer((BRIDGE_HOST, port), state)
    except OSError as exc:
        raise NativeBridgeUnavailable(
            f"native bridge port {port} is unavailable: {exc}"
        ) from exc
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.05},
        daemon=True,
    )
    thread.start()
    try:
        if not _wait_for(state.delivered_event, connect_timeout, cancel_event):
            raise NativeBridgeUnavailable(
                "native bridge extension did not connect before timeout"
            )
        if not _wait_for(state.result_event, result_timeout, cancel_event):
            raise NativeBridgeCommandError("native bridge result timeout")
        return _validate_response(state.response)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def probe_native_bridge(*, home: Path | None = None) -> dict[str, Any]:
    items = run_native_job(
        "system.ping",
        {},
        home=home,
        connect_timeout=1.0,
        result_timeout=2.0,
    )
    return items[0] if items else {"pong": True}
