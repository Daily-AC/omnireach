from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(autouse=True)
def isolated_preferences(monkeypatch, tmp_path_factory) -> Path:
    """Keep the developer's ~/.omnireach/preferences.toml out of every test.

    `[media].cookies_from_browser` now changes the yt-dlp argv, so a real
    preferences file on the machine running pytest would silently alter
    assertions that CI (which has no such file) makes on defaults.
    """
    path = tmp_path_factory.mktemp("omnireach-preferences") / "preferences.toml"
    monkeypatch.setattr("omnireach.preferences.preferences_path", lambda: path)
    return path
