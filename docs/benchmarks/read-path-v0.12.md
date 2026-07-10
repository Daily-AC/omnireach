# Read-Path Benchmark: omnireach MCP vs Playwright

Generated at `2026-07-10T10:26:19.446551Z` against [https://www.rfc-editor.org/rfc/rfc9110.html](https://www.rfc-editor.org/rfc/rfc9110.html).
Each value is the median of 5 measured runs. [Raw samples](./read-path-v0.12.json) are committed beside this report.

## Result

| Read path | Median | Minimum | Maximum |
|---|---:|---:|---:|
| omnireach MCP, cold process | 1425.26 ms | 1389.18 ms | 1494.21 ms |
| Playwright, cold headless system Chrome | 2713.69 ms | 2556.70 ms | 2940.93 ms |
| omnireach MCP, warm server | 1292.39 ms | 1248.84 ms | 1338.44 ms |
| Playwright, warm headless system Chrome | 1591.44 ms | 1555.50 ms | 1649.05 ms |

For this document on this machine, cold Playwright retrieval took **1.9x** the omnireach MCP time. With both runtimes already warm, Playwright took **1.2x** the omnireach MCP time.

## Method

- omnireach starts its real stdio MCP server and calls `omnireach_fetch` with the built-in HTTP extractor.
- Playwright launches the installed stable Chrome channel headlessly, navigates to the same URL, and reads `body.innerText`.
- Cold measurements include process or browser startup. Warm measurements reuse one MCP server or one browser. Playwright's warm browser cache remains enabled.
- Every response must return at least 500 text characters. Failed responses abort the run instead of disappearing from the samples.

This read-only retrieval benchmark does not compare clicks, forms, downloads, or visual testing. It demonstrates why agents should try a direct read path first, not that HTTP extraction replaces browser automation.

## Environment

| Component | Value |
|---|---|
| OS | `macOS-26.0.1-arm64-arm-64bit` |
| Architecture | `arm64` |
| Python | `3.12.13` |
| omnireach | `0.12.0-alpha` |
| Playwright | `1.61.0` |
| Chrome | `149.0.7827.201` |

## Reproduce

```bash
uv run --with playwright python scripts/benchmark_read_path.py \
  --repeat 5 \
  --json-out docs/benchmarks/read-path-v0.12.json \
  --markdown-out docs/benchmarks/read-path-v0.12.md
```
