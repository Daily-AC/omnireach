import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")
def test_native_extension_javascript_contracts():
    result = subprocess.run(
        ["node", "--test", str(ROOT / "tests/js/native-extension.test.mjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
