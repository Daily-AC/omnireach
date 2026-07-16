import json
import socket
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pytest

from omnireach.bridge_install import install_extension
from omnireach.native_bridge import (
    MAX_RESULT_BYTES,
    NATIVE_EXTENSION_MIN_VERSION,
    NativeBridgeCommandError,
    NativeBridgeUnavailable,
    run_native_job,
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request(
    port: int,
    token: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    path: str = "/v1/job",
    extension_version: str = NATIVE_EXTENSION_MIN_VERSION,
):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Omnireach-Extension-Version": extension_version,
        },
    )
    return urllib.request.urlopen(request, timeout=2)


def _poll_job(port: int, token: str) -> dict:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            with _request(port, token) as response:
                if response.status == 200:
                    return json.loads(response.read())
        except urllib.error.HTTPError:
            raise
        except (ConnectionError, urllib.error.URLError):
            time.sleep(0.02)
    raise AssertionError("bridge server did not expose a job")


def test_native_bridge_round_trip_with_simulated_extension(tmp_path):
    paths = install_extension(home=tmp_path)
    token = paths.token_path.read_text().strip()
    port = _free_port()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            run_native_job,
            "douyin.search",
            {"query": "gpt5.6", "limit": 2},
            home=tmp_path,
            port=port,
            connect_timeout=2,
            result_timeout=2,
        )
        job = _poll_job(port, token)
        assert job["command"] == "douyin.search"
        result = {
            "id": job["id"],
            "ok": True,
            "items": [{"desc": "real result", "url": "https://www.douyin.com/video/1"}],
        }
        with _request(
            port,
            token,
            method="POST",
            path="/v1/result",
            body=json.dumps(result).encode(),
        ) as response:
            assert response.status == 204

        assert future.result() == result["items"]


def test_native_bridge_rejects_wrong_token_then_accepts_correct_one(tmp_path):
    paths = install_extension(home=tmp_path)
    token = paths.token_path.read_text().strip()
    port = _free_port()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            run_native_job,
            "system.ping",
            {},
            home=tmp_path,
            port=port,
            connect_timeout=2,
            result_timeout=2,
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            _poll_job(port, "wrong-token")
        assert exc.value.code == 401

        job = _poll_job(port, token)
        result = {"id": job["id"], "ok": True, "items": [{"pong": True}]}
        with _request(
            port,
            token,
            method="POST",
            path="/v1/result",
            body=json.dumps(result).encode(),
        ):
            pass
        assert future.result() == [{"pong": True}]


def test_native_bridge_ignores_outdated_extension_pollers(tmp_path):
    paths = install_extension(home=tmp_path)
    token = paths.token_path.read_text().strip()
    port = _free_port()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            run_native_job,
            "tiktok.search",
            {"query": "python", "limit": 1},
            home=tmp_path,
            port=port,
            connect_timeout=2,
            result_timeout=2,
        )
        deadline = time.monotonic() + 2
        while True:
            try:
                with _request(
                    port, token, extension_version="0.1.1"
                ) as response:
                    assert response.status == 204
                break
            except (ConnectionError, urllib.error.URLError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)

        job = _poll_job(port, token)
        result = {"id": job["id"], "ok": True, "items": []}
        with _request(
            port,
            token,
            method="POST",
            path="/v1/result",
            body=json.dumps(result).encode(),
        ):
            pass
        assert future.result() == []


def test_native_bridge_rejects_wrong_result_id(tmp_path):
    paths = install_extension(home=tmp_path)
    token = paths.token_path.read_text().strip()
    port = _free_port()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            run_native_job,
            "system.ping",
            {},
            home=tmp_path,
            port=port,
            connect_timeout=2,
            result_timeout=2,
        )
        job = _poll_job(port, token)
        wrong = {"id": "wrong", "ok": True, "items": []}
        with pytest.raises(urllib.error.HTTPError) as exc:
            _request(
                port,
                token,
                method="POST",
                path="/v1/result",
                body=json.dumps(wrong).encode(),
            )
        assert exc.value.code == 409

        correct = {"id": job["id"], "ok": True, "items": []}
        with _request(
            port,
            token,
            method="POST",
            path="/v1/result",
            body=json.dumps(correct).encode(),
        ):
            pass
        assert future.result() == []


def test_native_bridge_rejects_oversized_result(tmp_path):
    paths = install_extension(home=tmp_path)
    token = paths.token_path.read_text().strip()
    port = _free_port()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            run_native_job,
            "system.ping",
            {},
            home=tmp_path,
            port=port,
            connect_timeout=2,
            result_timeout=2,
        )
        job = _poll_job(port, token)
        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            request = (
                "POST /v1/result HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{port}\r\n"
                f"Authorization: Bearer {token}\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {MAX_RESULT_BYTES + 1}\r\n"
                "Connection: close\r\n\r\n"
            )
            client.sendall(request.encode())
            response = client.recv(256)
        assert b" 413 " in response

        correct = {"id": job["id"], "ok": True, "items": []}
        with _request(
            port,
            token,
            method="POST",
            path="/v1/result",
            body=json.dumps(correct).encode(),
        ):
            pass
        assert future.result() == []


def test_native_bridge_connection_timeout_is_unavailable(tmp_path):
    install_extension(home=tmp_path)

    with pytest.raises(NativeBridgeUnavailable, match="extension did not connect"):
        run_native_job(
            "system.ping",
            {},
            home=tmp_path,
            port=_free_port(),
            connect_timeout=0.05,
            result_timeout=0.05,
        )


def test_native_bridge_result_timeout_is_command_error(tmp_path):
    paths = install_extension(home=tmp_path)
    token = paths.token_path.read_text().strip()
    port = _free_port()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            run_native_job,
            "system.ping",
            {},
            home=tmp_path,
            port=port,
            connect_timeout=2,
            result_timeout=0.05,
        )
        _poll_job(port, token)
        with pytest.raises(NativeBridgeCommandError, match="result timeout"):
            future.result()


def test_native_bridge_port_contention_is_unavailable(tmp_path):
    install_extension(home=tmp_path)
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = int(occupied.getsockname()[1])
        with pytest.raises(NativeBridgeUnavailable, match="port"):
            run_native_job(
                "system.ping",
                {},
                home=tmp_path,
                port=port,
                connect_timeout=0.05,
                result_timeout=0.05,
            )


def test_native_bridge_reuses_fixed_port_after_completed_job(tmp_path):
    paths = install_extension(home=tmp_path)
    token = paths.token_path.read_text().strip()
    port = _free_port()

    def run_once() -> None:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                run_native_job,
                "system.ping",
                {},
                home=tmp_path,
                port=port,
                connect_timeout=2,
                result_timeout=2,
            )
            job = _poll_job(port, token)
            result = {"id": job["id"], "ok": True, "items": [{"pong": True}]}
            with _request(
                port,
                token,
                method="POST",
                path="/v1/result",
                body=json.dumps(result).encode(),
            ):
                pass
            assert future.result() == [{"pong": True}]

    run_once()
    run_once()


def test_native_bridge_serializes_concurrent_jobs_on_fixed_port(tmp_path):
    paths = install_extension(home=tmp_path)
    token = paths.token_path.read_text().strip()
    port = _free_port()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                run_native_job,
                command,
                {"query": command},
                home=tmp_path,
                port=port,
                connect_timeout=2,
                result_timeout=2,
            )
            for command in ("google.search", "twitter.search")
        ]
        seen_commands = set()
        for _ in range(2):
            job = _poll_job(port, token)
            seen_commands.add(job["command"])
            result = {
                "id": job["id"],
                "ok": True,
                "items": [{"command": job["command"]}],
            }
            with _request(
                port,
                token,
                method="POST",
                path="/v1/result",
                body=json.dumps(result).encode(),
            ):
                pass

        assert seen_commands == {"google.search", "twitter.search"}
        assert {
            future.result()[0]["command"] for future in futures
        } == seen_commands


def test_native_bridge_cancellation_stops_waiting(tmp_path):
    install_extension(home=tmp_path)
    cancel = threading.Event()
    cancel.set()

    with pytest.raises(NativeBridgeUnavailable, match="cancelled"):
        run_native_job(
            "system.ping",
            {},
            home=tmp_path,
            port=_free_port(),
            connect_timeout=1,
            result_timeout=1,
            cancel_event=cancel,
        )
