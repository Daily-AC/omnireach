import asyncio
import json

import pytest

from omnireach.adapters._opencli import OpenCLICommandError, run_opencli_json
from omnireach.adapters.base import AdapterUnavailable


async def test_opencli_bridge_forces_silent_ephemeral_tab(monkeypatch):
    captured: list[str] = []

    async def fake_exec(*args, **kwargs):
        captured.extend(args)

        class P:
            returncode = 0

            async def communicate(self):
                return json.dumps([{"ok": True}]).encode(), b""

        return P()

    monkeypatch.setattr("omnireach.adapters._opencli.shutil.which", lambda n: "/bin/opencli")
    monkeypatch.setattr(
        "omnireach.adapters._opencli.asyncio.create_subprocess_exec", fake_exec
    )

    out = await run_opencli_json("twitter", "twitter", "search", "query")

    assert out == [{"ok": True}]
    assert captured[captured.index("--window") + 1] == "background"
    assert captured[captured.index("--site-session") + 1] == "ephemeral"
    assert captured[captured.index("--keep-tab") + 1] == "false"
    assert captured[captured.index("--format") + 1] == "json"


async def test_opencli_bridge_terminates_child_when_dispatcher_cancels(monkeypatch):
    started = asyncio.Event()

    class P:
        returncode = None
        terminated = False
        waited = False

        async def communicate(self):
            started.set()
            await asyncio.Event().wait()

        def terminate(self):
            self.terminated = True
            self.returncode = -15

        async def wait(self):
            self.waited = True
            return self.returncode

    proc = P()
    monkeypatch.setattr("omnireach.adapters._opencli.shutil.which", lambda n: "/bin/opencli")
    monkeypatch.setattr(
        "omnireach.adapters._opencli.asyncio.create_subprocess_exec",
        lambda *a, **kw: asyncio.sleep(0, result=proc),
    )

    task = asyncio.create_task(
        run_opencli_json("twitter", "twitter", "search", "query")
    )
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert proc.terminated is True
    assert proc.waited is True


async def test_opencli_bridge_rejects_valid_json_with_wrong_shape(monkeypatch):
    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return b'"not-a-result-list"', b""

        return P()

    monkeypatch.setattr("omnireach.adapters._opencli.shutil.which", lambda n: "/bin/opencli")
    monkeypatch.setattr(
        "omnireach.adapters._opencli.asyncio.create_subprocess_exec", fake_exec
    )

    with pytest.raises(OpenCLICommandError, match="invalid result shape"):
        await run_opencli_json("twitter", "twitter", "search", "query")


async def test_opencli_bridge_nonzero_is_execution_error(monkeypatch):
    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 1

            async def communicate(self):
                return b"", b"Chrome bridge disconnected"

        return P()

    monkeypatch.setattr(
        "omnireach.adapters._opencli.shutil.which", lambda _: "/bin/opencli"
    )
    monkeypatch.setattr(
        "omnireach.adapters._opencli.asyncio.create_subprocess_exec", fake_exec
    )

    with pytest.raises(OpenCLICommandError, match="Chrome bridge disconnected"):
        await run_opencli_json("douyin", "douyin", "search", "gpt5.6")


async def test_opencli_bridge_malformed_json_is_execution_error(monkeypatch):
    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return b"not-json", b""

        return P()

    monkeypatch.setattr(
        "omnireach.adapters._opencli.shutil.which", lambda _: "/bin/opencli"
    )
    monkeypatch.setattr(
        "omnireach.adapters._opencli.asyncio.create_subprocess_exec", fake_exec
    )

    with pytest.raises(OpenCLICommandError, match="non-JSON"):
        await run_opencli_json("douyin", "douyin", "search", "gpt5.6")


async def test_opencli_bridge_missing_binary_stays_unavailable(monkeypatch):
    monkeypatch.setattr("omnireach.adapters._opencli.shutil.which", lambda _: None)

    with pytest.raises(AdapterUnavailable, match="opencli not installed"):
        await run_opencli_json("douyin", "douyin", "search", "gpt5.6")
