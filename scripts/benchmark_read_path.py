#!/usr/bin/env python3
"""Benchmark omnireach MCP fetch against Playwright with system Chrome."""

from __future__ import annotations

import argparse
import json
import platform
import shlex
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from omnireach import __version__

MIN_TEXT_LENGTH = 500
DEFAULT_URL = "https://www.rfc-editor.org/rfc/rfc9110.html"
MCP_COMMAND = [sys.executable, "-m", "omnireach", "mcp"]


def validate_text(text: str) -> None:
    """Reject responses too small to represent a successful document read."""
    if len(text.strip()) < MIN_TEXT_LENGTH:
        raise RuntimeError(
            f"retrieved fewer than {MIN_TEXT_LENGTH} text characters"
        )


def summarize_samples(samples: list[float]) -> dict[str, object]:
    """Return stable summary statistics while preserving every raw sample."""
    if not samples:
        raise ValueError("at least one benchmark sample is required")
    rounded = [round(value, 2) for value in samples]
    return {
        "median_ms": round(statistics.median(rounded), 2),
        "min_ms": min(rounded),
        "max_ms": max(rounded),
        "samples_ms": rounded,
    }


def _write_message(proc: subprocess.Popen[str], message: dict[str, Any]) -> None:
    if proc.stdin is None:
        raise RuntimeError("MCP stdin is unavailable")
    proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def send_message(
    proc: subprocess.Popen[str],
    message: dict[str, Any],
) -> dict[str, Any]:
    """Send one JSON-RPC request and read one response from stdio."""
    _write_message(proc, message)
    if proc.stdout is None:
        raise RuntimeError("MCP stdout is unavailable")
    line = proc.stdout.readline()
    if not line:
        stderr = proc.stderr.read() if proc.stderr is not None else ""
        raise RuntimeError(f"MCP process exited before responding: {stderr}")
    payload = json.loads(line)
    if not isinstance(payload, dict):
        raise RuntimeError("MCP response is not a JSON object")
    return payload


def start_mcp() -> subprocess.Popen[str]:
    """Start and initialize the real omnireach stdio server."""
    proc = subprocess.Popen(
        MCP_COMMAND,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    initialized = send_message(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {
                    "name": "omnireach-read-path-benchmark",
                    "version": "1",
                },
            },
        },
    )
    if initialized.get("result", {}).get("protocolVersion") != "2025-06-18":
        stop_mcp(proc)
        raise RuntimeError(f"unexpected MCP initialize response: {initialized}")
    _write_message(
        proc,
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
    )
    return proc


def stop_mcp(proc: subprocess.Popen[str]) -> None:
    """Close stdin and require a clean stdio-server shutdown."""
    if proc.stdin is not None and not proc.stdin.closed:
        proc.stdin.close()
    try:
        returncode = proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        raise RuntimeError("MCP process did not stop after stdin closed") from None
    if returncode != 0:
        stderr = proc.stderr.read() if proc.stderr is not None else ""
        raise RuntimeError(f"MCP process exited {returncode}: {stderr}")


def mcp_fetch(proc: subprocess.Popen[str], url: str, request_id: int) -> str:
    """Call the real omnireach_fetch MCP tool and validate its body."""
    response = send_message(
        proc,
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": "omnireach_fetch",
                "arguments": {
                    "url": url,
                    "backend": "http",
                    "timeout": 60,
                },
            },
        },
    )
    if "error" in response:
        raise RuntimeError(f"MCP error: {response['error']}")
    result = response.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"missing MCP tool result: {response}")
    if result.get("isError"):
        raise RuntimeError(f"omnireach_fetch failed: {result}")
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        raise RuntimeError("MCP tool result has no structuredContent")
    text = structured.get("content_markdown")
    if not isinstance(text, str):
        raise RuntimeError("MCP tool result has no Markdown body")
    validate_text(text)
    return text


def benchmark_mcp_cold(url: str, repetitions: int) -> tuple[list[float], list[int]]:
    """Measure process startup, initialize, and one MCP fetch per sample."""
    samples: list[float] = []
    sizes: list[int] = []
    for sample_index in range(repetitions):
        started = time.perf_counter()
        proc = start_mcp()
        try:
            text = mcp_fetch(proc, url, request_id=sample_index + 2)
            elapsed = (time.perf_counter() - started) * 1000
        finally:
            stop_mcp(proc)
        samples.append(elapsed)
        sizes.append(len(text))
    return samples, sizes


def benchmark_mcp_warm(url: str, repetitions: int) -> tuple[list[float], list[int]]:
    """Measure repeated calls through one initialized MCP server."""
    samples: list[float] = []
    sizes: list[int] = []
    proc = start_mcp()
    try:
        mcp_fetch(proc, url, request_id=2)
        for sample_index in range(repetitions):
            started = time.perf_counter()
            text = mcp_fetch(proc, url, request_id=sample_index + 3)
            elapsed = (time.perf_counter() - started) * 1000
            samples.append(elapsed)
            sizes.append(len(text))
    finally:
        stop_mcp(proc)
    return samples, sizes


def read_with_page(page: Any, url: str) -> str:
    """Navigate one Playwright page and extract visible body text."""
    response = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    if response is None or not 200 <= response.status < 400:
        status = None if response is None else response.status
        raise RuntimeError(f"Playwright navigation returned status {status}")
    text = page.locator("body").inner_text(timeout=60_000)
    validate_text(text)
    return text


def benchmark_playwright_cold(
    url: str,
    repetitions: int,
) -> tuple[list[float], list[int], str]:
    """Measure driver and headless system-Chrome startup for every read."""
    from playwright.sync_api import sync_playwright

    samples: list[float] = []
    sizes: list[int] = []
    chrome_version = "unknown"
    for _ in range(repetitions):
        started = time.perf_counter()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            try:
                chrome_version = browser.version
                page = browser.new_page()
                try:
                    text = read_with_page(page, url)
                finally:
                    page.close()
            finally:
                browser.close()
        samples.append((time.perf_counter() - started) * 1000)
        sizes.append(len(text))
    return samples, sizes, chrome_version


def benchmark_playwright_warm(
    url: str,
    repetitions: int,
) -> tuple[list[float], list[int], str]:
    """Measure navigation through one persistent headless system Chrome."""
    from playwright.sync_api import sync_playwright

    samples: list[float] = []
    sizes: list[int] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            chrome_version = browser.version
            warmup = browser.new_page()
            try:
                read_with_page(warmup, url)
            finally:
                warmup.close()
            for _ in range(repetitions):
                page = browser.new_page()
                try:
                    started = time.perf_counter()
                    text = read_with_page(page, url)
                    samples.append((time.perf_counter() - started) * 1000)
                    sizes.append(len(text))
                finally:
                    page.close()
        finally:
            browser.close()
    return samples, sizes, chrome_version


def _ratio(numerator: float, denominator: float) -> str:
    if denominator <= 0:
        raise ValueError("ratio denominator must be positive")
    return f"{numerator / denominator:.1f}x"


def render_report(payload: dict[str, Any]) -> str:
    """Render the public Markdown report from raw benchmark data."""
    results = payload["results"]
    mcp_cold = results["omnireach_mcp_cold"]
    mcp_warm = results["omnireach_mcp_warm"]
    browser_cold = results["playwright_chrome_cold"]
    browser_warm = results["playwright_chrome_warm"]
    cold_ratio = _ratio(browser_cold["median_ms"], mcp_cold["median_ms"])
    warm_ratio = _ratio(browser_warm["median_ms"], mcp_warm["median_ms"])
    environment = payload["environment"]
    return f"""# Read-Path Benchmark: omnireach MCP vs Playwright

Generated at `{payload['generated_at']}` against [{payload['target_url']}]({payload['target_url']}).
Each value is the median of {payload['repetitions']} measured runs. [Raw samples](./read-path-v0.12.json) are committed beside this report.

## Result

| Read path | Median | Minimum | Maximum |
|---|---:|---:|---:|
| omnireach MCP, cold process | {mcp_cold['median_ms']:.2f} ms | {mcp_cold['min_ms']:.2f} ms | {mcp_cold['max_ms']:.2f} ms |
| Playwright, cold headless system Chrome | {browser_cold['median_ms']:.2f} ms | {browser_cold['min_ms']:.2f} ms | {browser_cold['max_ms']:.2f} ms |
| omnireach MCP, warm server | {mcp_warm['median_ms']:.2f} ms | {mcp_warm['min_ms']:.2f} ms | {mcp_warm['max_ms']:.2f} ms |
| Playwright, warm headless system Chrome | {browser_warm['median_ms']:.2f} ms | {browser_warm['min_ms']:.2f} ms | {browser_warm['max_ms']:.2f} ms |

For this document on this machine, cold Playwright retrieval took **{cold_ratio}** the omnireach MCP time. With both runtimes already warm, Playwright took **{warm_ratio}** the omnireach MCP time.

## Method

- omnireach starts its real stdio MCP server and calls `omnireach_fetch` with the built-in HTTP extractor.
- Playwright launches the installed stable Chrome channel headlessly, navigates to the same URL, and reads `body.innerText`.
- Cold measurements include process or browser startup. Warm measurements reuse one MCP server or one browser. Playwright's warm browser cache remains enabled.
- Every response must return at least {MIN_TEXT_LENGTH} text characters. Failed responses abort the run instead of disappearing from the samples.

This read-only retrieval benchmark does not compare clicks, forms, downloads, or visual testing. It demonstrates why agents should try a direct read path first, not that HTTP extraction replaces browser automation.

## Environment

| Component | Value |
|---|---|
| OS | `{environment['os']}` |
| Architecture | `{environment['architecture']}` |
| Python | `{environment['python']}` |
| omnireach | `{environment['omnireach']}` |
| Playwright | `{environment['playwright']}` |
| Chrome | `{environment['chrome']}` |

## Reproduce

```bash
uv run --with playwright python scripts/benchmark_read_path.py \\
  --repeat {payload['repetitions']} \\
  --json-out docs/benchmarks/read-path-v0.12.json \\
  --markdown-out docs/benchmarks/read-path-v0.12.md
```
"""


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "not installed"


def portable_command(arguments: list[str]) -> str:
    """Render a reproducible command without local interpreter paths."""
    return shlex.join(["python", *arguments])


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def run_benchmark(
    url: str,
    repetitions: int,
    *,
    skip_playwright: bool = False,
) -> dict[str, Any]:
    """Execute every selected path and return one serializable payload."""
    mcp_cold, mcp_cold_sizes = benchmark_mcp_cold(url, repetitions)
    mcp_warm, mcp_warm_sizes = benchmark_mcp_warm(url, repetitions)
    results: dict[str, Any] = {
        "omnireach_mcp_cold": summarize_samples(mcp_cold),
        "omnireach_mcp_warm": summarize_samples(mcp_warm),
    }
    content_sizes: dict[str, list[int]] = {
        "omnireach_mcp_cold": mcp_cold_sizes,
        "omnireach_mcp_warm": mcp_warm_sizes,
    }
    chrome_version = "not run"
    if not skip_playwright:
        browser_cold, browser_cold_sizes, chrome_version = (
            benchmark_playwright_cold(url, repetitions)
        )
        browser_warm, browser_warm_sizes, warm_chrome_version = (
            benchmark_playwright_warm(url, repetitions)
        )
        if warm_chrome_version != chrome_version:
            raise RuntimeError(
                "Chrome version changed between cold and warm benchmark paths"
            )
        results.update(
            {
                "playwright_chrome_cold": summarize_samples(browser_cold),
                "playwright_chrome_warm": summarize_samples(browser_warm),
            }
        )
        content_sizes.update(
            {
                "playwright_chrome_cold": browser_cold_sizes,
                "playwright_chrome_warm": browser_warm_sizes,
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "target_url": url,
        "repetitions": repetitions,
        "command": portable_command(sys.argv),
        "environment": {
            "os": platform.platform(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "omnireach": __version__,
            "playwright": (
                "not run" if skip_playwright else _package_version("playwright")
            ),
            "chrome": chrome_version,
        },
        "results": results,
        "content_characters": content_sizes,
    }


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--repeat", type=_positive_integer, default=5)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--skip-playwright", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = run_benchmark(
        args.url,
        args.repeat,
        skip_playwright=args.skip_playwright,
    )
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        _atomic_write(args.json_out, serialized)
    if args.markdown_out:
        if args.skip_playwright:
            raise RuntimeError(
                "cannot render the comparison report when Playwright is skipped"
            )
        _atomic_write(args.markdown_out, render_report(payload))
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
