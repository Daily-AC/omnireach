"""Experimental adapter for Antigravity CLI's server-side grounded search."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult

_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_SOURCE_RE = re.compile(r"^\[(\d+)]\s+\[([^]]+)]\((https?://[^)]+)\)\s*$")
_HTTP_PORT_RE = re.compile(
    r"Language server listening on random port at (\d+) for HTTP\s*$"
)


@dataclass(frozen=True)
class GroundedSearchResponse:
    conversation_id: str
    summary: str
    sources: list[tuple[str, str]]


def _agentapi_command() -> tuple[str, ...] | None:
    configured = os.environ.get("OMNIREACH_AGY_AGENTAPI", "").strip()
    if configured:
        return (configured,)
    standalone = shutil.which("agentapi")
    if standalone:
        return (standalone,)
    bundled = Path.home() / ".gemini" / "antigravity-cli" / "bin" / "agentapi"
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return (str(bundled),)
    agy = shutil.which("agy")
    if agy:
        return (agy, "agentapi")
    return None


def _agy_home() -> Path:
    return Path(
        os.environ.get(
            "OMNIREACH_AGY_HOME",
            str(Path.home() / ".gemini" / "antigravity-cli"),
        )
    )


def _port_is_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.1):
            return True
    except OSError:
        return False


def _agentapi_address() -> str | None:
    configured = os.environ.get("ANTIGRAVITY_LS_ADDRESS", "").strip()
    if configured:
        return configured
    log_dir = _agy_home() / "log"
    try:
        logs = sorted(
            log_dir.glob("cli-*.log"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return None
    for log_path in logs[:10]:
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            match = _HTTP_PORT_RE.search(line)
            if match is None:
                continue
            port = int(match.group(1))
            if _port_is_open(port):
                return f"localhost:{port}"
            break
    return None


def _transcript_path(conversation_id: str) -> Path:
    root = _agy_home()
    return (
        root
        / "brain"
        / conversation_id
        / ".system_generated"
        / "logs"
        / "transcript_full.jsonl"
    )


def _conversation_config_path() -> Path:
    return Path.home() / ".omnireach" / "agy-conversation"


def configured_conversation_id() -> str | None:
    configured = os.environ.get("OMNIREACH_AGY_CONVERSATION", "").strip()
    if not configured:
        try:
            configured = _conversation_config_path().read_text(encoding="utf-8").strip()
        except OSError:
            return None
    return configured if _UUID_RE.fullmatch(configured) else None


def configure_conversation(conversation_id: str) -> Path:
    if _UUID_RE.fullmatch(conversation_id) is None:
        raise ValueError("conversation id must be a UUID")
    transcript = _transcript_path(conversation_id)
    if not transcript.is_file():
        raise ValueError(f"agy conversation does not exist: {conversation_id}")
    path = _conversation_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    path.write_text(conversation_id + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def clear_configured_conversation() -> Path:
    path = _conversation_config_path()
    path.unlink(missing_ok=True)
    return path


def _latest_step_index(transcript: Path) -> int:
    if not transcript.is_file():
        return -1
    latest = -1
    try:
        lines = transcript.read_text(encoding="utf-8").splitlines()
    except OSError:
        return -1
    for line in lines:
        try:
            step = json.loads(line)
        except json.JSONDecodeError:
            continue
        index = step.get("step_index")
        if isinstance(index, int):
            latest = max(latest, index)
    return latest


async def _send_grounded_request(query: str, conversation_id: str) -> int:
    command = _agentapi_command()
    address = _agentapi_address()
    if command is None or address is None:
        raise AdapterUnavailable(
            "agy",
            "agy agentapi is unavailable; keep an authenticated agy CLI process running",
            hint="start agy in a terminal, then retry `omnireach search ... --on agy`",
        )

    prompt = (
        "Use the built-in WebSearch tool exactly once to search this query: "
        f"{json.dumps(query, ensure_ascii=False)}. "
        "Return a concise grounded summary with the WebSearch citations. "
        "Do not edit files, run shell commands, or use any other tools."
    )
    transcript = _transcript_path(conversation_id)
    baseline = _latest_step_index(transcript)
    proc = await asyncio.create_subprocess_exec(
        *command,
        "send-message",
        "--title=Omnireach grounded search",
        conversation_id,
        prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "ANTIGRAVITY_LS_ADDRESS": address},
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20.0)
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise AdapterUnavailable("agy", "agentapi did not accept the search request within 20s") from exc
    output = "\n".join(
        part.decode("utf-8", errors="replace") for part in (stdout, stderr) if part
    )
    if proc.returncode != 0:
        raise AdapterUnavailable("agy", output.strip() or "agentapi send-message failed")
    try:
        payload = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterUnavailable(
            "agy", "agentapi send-message returned invalid JSON"
        ) from exc
    if payload.get("error"):
        raise AdapterUnavailable("agy", str(payload["error"]))
    recipient = (
        payload.get("response", {})
        .get("sendMessage", {})
        .get("recipientId")
    )
    if recipient != conversation_id:
        raise AdapterUnavailable("agy", "agentapi did not acknowledge the target conversation")
    return baseline


def parse_grounded_content(content: str) -> tuple[str, list[tuple[str, str]]]:
    """Parse the observed SEARCH_WEB transcript format into summary + citations."""
    if not isinstance(content, str) or not content.strip():
        raise ValueError("agy SEARCH_WEB step has empty content")

    lines = content.splitlines()
    source_index = next(
        (index for index, line in enumerate(lines) if line.strip() == "Sources:"),
        None,
    )
    if source_index is None:
        raise ValueError("agy SEARCH_WEB step does not contain a Sources section")

    summary_lines = lines[:source_index]
    summary_start = next(
        (
            index + 1
            for index, line in enumerate(summary_lines)
            if line.startswith("The search for ")
            and line.endswith("returned the following summary:")
        ),
        0,
    )
    summary = "\n".join(summary_lines[summary_start:]).strip()

    sources: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in lines[source_index + 1 :]:
        match = _SOURCE_RE.match(line.strip())
        if not match:
            continue
        title, url = match.group(2).strip(), match.group(3).strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or url in seen:
            continue
        seen.add(url)
        sources.append((title, url))

    if not summary:
        raise ValueError("agy SEARCH_WEB step has no summary")
    if not sources:
        raise ValueError("agy SEARCH_WEB step has no valid citations")
    return summary, sources


def read_grounded_response(
    transcript: Path,
    conversation_id: str,
    *,
    after_step_index: int = -1,
) -> GroundedSearchResponse | None:
    """Return the latest completed SEARCH_WEB step, or None while still pending."""
    if not transcript.is_file():
        return None
    latest: dict[str, object] | None = None
    try:
        lines = transcript.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AdapterUnavailable("agy", f"cannot read agy transcript: {exc}") from exc
    for line in lines:
        try:
            step = json.loads(line)
        except json.JSONDecodeError:
            continue
        index = step.get("step_index")
        if (
            step.get("type") == "SEARCH_WEB"
            and step.get("status") == "DONE"
            and isinstance(index, int)
            and index > after_step_index
        ):
            latest = step
    if latest is not None:
        try:
            summary, sources = parse_grounded_content(str(latest.get("content") or ""))
        except ValueError as exc:
            raise AdapterUnavailable("agy", str(exc)) from exc
        return GroundedSearchResponse(conversation_id, summary, sources)
    # Agy may recover from a transient ERROR_MESSAGE in the same trajectory;
    # the captured real session did exactly that before its SEARCH_WEB step.
    return None


async def run_grounded_search(
    query: str,
    *,
    timeout: float = 75.0,
    poll_interval: float = 0.5,
) -> GroundedSearchResponse:
    conversation_id = configured_conversation_id()
    if conversation_id is None:
        raise AdapterUnavailable(
            "agy",
            "no dedicated agy conversation is configured",
            hint="run `omnireach agy configure <conversation-id>`",
        )
    transcript = _transcript_path(conversation_id)
    baseline = await _send_grounded_request(query, conversation_id)
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        response = read_grounded_response(
            transcript, conversation_id, after_step_index=baseline
        )
        if response is not None:
            return response
        await asyncio.sleep(poll_interval)
    raise AdapterUnavailable(
        "agy",
        f"grounded search did not finish within {timeout:.0f}s (conversation {conversation_id})",
    )


class AgyGroundedAdapter(AdapterBase):
    name = "agy"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return (
            configured_conversation_id() is not None
            and _agentapi_command() is not None
            and _agentapi_address() is not None
        )

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        response = await run_grounded_search(query)
        results: list[SearchResult] = []
        for index, (title, url) in enumerate(response.sources[:limit]):
            results.append(
                SearchResult(
                    source="agy",
                    adapter="agy-grounded-search",
                    title=title,
                    url=url,
                    content=response.summary if index == 0 else "",
                    score=0.5,
                    raw={
                        "citation_index": index + 1,
                        "conversation_id": response.conversation_id,
                        "summary": response.summary,
                    },
                )
            )
        return results
