"""omnireach check-update — compare local __version__ to latest GitHub release."""

from __future__ import annotations

import click
import httpx

from omnireach import __version__

RELEASES_API = "https://api.github.com/repos/Daily-AC/omnireach/releases/latest"
UPGRADE_CMD = "uv tool install --force git+https://github.com/Daily-AC/omnireach.git"


def _strip_v(tag: str) -> str:
    return tag[1:] if tag.startswith("v") else tag


@click.command("check-update")
def check_update_cmd() -> None:
    """检查 omnireach 是否有新版本可用 (调 GitHub Releases API)."""
    click.echo(f"当前版本: {__version__}")
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True) as client:
            resp = client.get(
                RELEASES_API,
                headers={"Accept": "application/vnd.github+json"},
            )
    except httpx.HTTPError as e:
        click.echo(f"⚠️  无法连接 GitHub: {e}")
        return
    if resp.status_code != 200:
        click.echo(f"⚠️  检查失败: GitHub 返回 {resp.status_code}")
        return
    data = resp.json()
    latest_tag = data.get("tag_name") or ""
    latest = _strip_v(latest_tag)
    if not latest:
        click.echo("⚠️  无法解析 latest release tag")
        return
    if latest == __version__:
        click.echo(f"✅ 已是最新 ({latest_tag}).")
        return
    release_url = data.get("html_url") or ""
    click.echo(f"🆕 有新版本: {latest_tag}")
    if release_url:
        click.echo(f"   release notes: {release_url}")
    click.echo()
    click.echo("升级:")
    click.echo(f"   {UPGRADE_CMD}")
