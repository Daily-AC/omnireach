import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "benchmark_read_path.py"


def _load_module():
    assert SCRIPT.exists(), "benchmark_read_path.py has not been implemented"
    spec = importlib.util.spec_from_file_location("benchmark_read_path", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summarize_samples_uses_median_and_preserves_raw_values():
    module = _load_module()

    summary = module.summarize_samples([40.0, 10.0, 20.0])

    assert summary == {
        "median_ms": 20.0,
        "min_ms": 10.0,
        "max_ms": 40.0,
        "samples_ms": [40.0, 10.0, 20.0],
    }


def test_summarize_samples_requires_at_least_one_sample():
    module = _load_module()

    with pytest.raises(ValueError, match="at least one"):
        module.summarize_samples([])


@pytest.mark.parametrize("text", ["", "tiny"])
def test_validate_text_rejects_empty_or_too_short_content(text):
    module = _load_module()

    with pytest.raises(RuntimeError, match="fewer than 500"):
        module.validate_text(text)


def test_validate_text_accepts_a_real_document_body():
    module = _load_module()

    module.validate_text("x" * 500)


def test_portable_command_omits_interpreter_and_cache_paths():
    module = _load_module()

    command = module.portable_command(
        [
            "scripts/benchmark_read_path.py",
            "--repeat",
            "5",
            "--json-out",
            "docs/benchmarks/read-path-v0.12.json",
        ]
    )

    assert command == (
        "python scripts/benchmark_read_path.py --repeat 5 "
        "--json-out docs/benchmarks/read-path-v0.12.json"
    )
    assert "/Users/" not in command
    assert ".cache/uv" not in command


def test_render_report_uses_measured_medians_and_scope():
    module = _load_module()
    payload = {
        "generated_at": "2026-07-10T00:00:00Z",
        "target_url": "https://example.com/article",
        "repetitions": 3,
        "environment": {
            "os": "macOS",
            "architecture": "arm64",
            "python": "3.12.1",
            "omnireach": "0.12.0-alpha",
            "playwright": "1.55.0",
            "chrome": "140.0.0.0",
        },
        "results": {
            "omnireach_mcp_cold": module.summarize_samples([100, 110, 120]),
            "omnireach_mcp_warm": module.summarize_samples([20, 30, 40]),
            "playwright_chrome_cold": module.summarize_samples([1000, 1100, 1200]),
            "playwright_chrome_warm": module.summarize_samples([200, 300, 400]),
        },
    }

    report = module.render_report(payload)

    assert report.count("10.0x") >= 2
    assert "headless system Chrome" in report
    assert (
        "does not compare clicks, forms, downloads, or visual testing" in report
    )
    assert "[Raw samples](./read-path-v0.12.json)" in report
