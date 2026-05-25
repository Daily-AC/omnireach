from unittest.mock import patch

import httpx
from click.testing import CliRunner

from omnireach.cli import main


def _mock_transport(status: int, json_body: dict | list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body if json_body is not None else {})
    return httpx.MockTransport(handler)


def test_check_update_when_up_to_date():
    from omnireach import __version__
    payload = {"tag_name": f"v{__version__}", "html_url": "https://x"}
    real_client = httpx.Client(transport=_mock_transport(200, payload))
    with patch("omnireach.commands.check_update.httpx.Client") as mock_cls:
        mock_cls.return_value.__enter__.return_value = real_client
        runner = CliRunner()
        result = runner.invoke(main, ["check-update"])
    assert result.exit_code == 0
    assert "已是最新" in result.output or "up to date" in result.output.lower()


def test_check_update_when_newer_available():
    payload = {"tag_name": "v99.0.0-alpha", "html_url": "https://github.com/Daily-AC/omnireach/releases/tag/v99.0.0-alpha"}
    real_client = httpx.Client(transport=_mock_transport(200, payload))
    with patch("omnireach.commands.check_update.httpx.Client") as mock_cls:
        mock_cls.return_value.__enter__.return_value = real_client
        runner = CliRunner()
        result = runner.invoke(main, ["check-update"])
    assert result.exit_code == 0
    assert "99.0.0-alpha" in result.output
    assert "uv tool install --force" in result.output


def test_check_update_handles_network_error():
    def handler(request):
        raise httpx.ConnectError("boom")
    real_client = httpx.Client(transport=httpx.MockTransport(handler))
    with patch("omnireach.commands.check_update.httpx.Client") as mock_cls:
        mock_cls.return_value.__enter__.return_value = real_client
        runner = CliRunner()
        result = runner.invoke(main, ["check-update"])
    # Network failure is non-fatal — exit 0, print warning
    assert result.exit_code == 0
    assert "无法连接" in result.output or "error" in result.output.lower() or "失败" in result.output


def test_check_update_handles_non_200():
    real_client = httpx.Client(transport=_mock_transport(500))
    with patch("omnireach.commands.check_update.httpx.Client") as mock_cls:
        mock_cls.return_value.__enter__.return_value = real_client
        runner = CliRunner()
        result = runner.invoke(main, ["check-update"])
    assert result.exit_code == 0
    assert "500" in result.output or "失败" in result.output
