"""omnireach fetch <url> — get full markdown content from a URL (v0.10).

Backends (dual-backend pattern, same as wechat/bilibili adapters):
- `crwl` (Crawl4AI, local install): preferred, 内置反爬
- `jina` (r.jina.ai SaaS): zero-config fallback, 免费额度大

CLI:
    omnireach fetch <url>                  # auto: crwl → jina fallback
    omnireach fetch <url> --backend crwl   # crwl only, fail if not installed
    omnireach fetch <url> --backend jina   # jina only
    omnireach fetch <url> --json           # explicit JSON output
"""

from __future__ import annotations

import json as _json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import click
import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()

JINA_BASE = "https://r.jina.ai/"


def _should_emit_json(explicit_flag: bool) -> bool:
    """v0.9.2 + v0.10: explicit flag wins; OMNIREACH_FORCE_JSON=1 also wins; else isatty."""
    if explicit_flag:
        return True
    if os.environ.get("OMNIREACH_FORCE_JSON", "").lower() in ("1", "true", "yes"):
        return True
    return not sys.stdout.isatty()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fetch_via_crwl(url: str, timeout: float) -> str:
    """Shell out to `crwl <url> -o markdown`. Returns markdown body or raises."""
    if not shutil.which("crwl"):
        raise RuntimeError("crwl 不在 PATH (跑 `pip install -U crawl4ai && crawl4ai-setup`)")
    proc = subprocess.run(
        ["crwl", url, "-o", "markdown"],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip()[:300] or f"exit {proc.returncode}"
        raise RuntimeError(f"crwl 失败: {err}")
    body = proc.stdout
    if not body.strip():
        raise RuntimeError("crwl 返回空内容")
    return body


def _fetch_via_jina(url: str, timeout: float) -> str:
    """GET https://r.jina.ai/<url> — Jina Reader SaaS, 返 markdown 文本。"""
    target = JINA_BASE + url
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as c:
            resp = c.get(target, headers={"Accept": "text/markdown"})
    except httpx.HTTPError as e:
        raise RuntimeError(f"jina http error: {e}") from e
    if resp.status_code >= 400:
        raise RuntimeError(f"jina 返回 {resp.status_code}")
    if not resp.text.strip():
        raise RuntimeError("jina 返回空内容")
    return resp.text


@click.command("fetch")
@click.argument("url")
@click.option("--backend", type=click.Choice(["auto", "crwl", "jina"]), default="auto",
              help="auto = crwl 优先, 失败/没装 fallback jina; 或显式指定")
@click.option("--json", "json_out", is_flag=True, help="输出 JSON envelope, 适合下游 pipe")
@click.option("--timeout", type=float, default=30.0, help="单 backend 超时秒数")
def fetch_cmd(url: str, backend: str, json_out: bool, timeout: float) -> None:
    """获取 URL 的全文 markdown.

    omnireach search 返 metadata + URL; omnireach fetch 把 URL 变成全文 markdown.
    Backend: crwl (Crawl4AI, 本地) 优先, 失败或没装走 jina (r.jina.ai SaaS) fallback.

    示例:
        omnireach fetch https://mp.weixin.qq.com/s/abc
        omnireach search --on wechat "claude" --json | \\
            jq -r '.results[].url' | xargs -I{} omnireach fetch {} --json
    """
    backends_to_try = ["crwl", "jina"] if backend == "auto" else [backend]
    content = ""
    used_backend = ""
    errors: list[str] = []

    for b in backends_to_try:
        try:
            if b == "crwl":
                content = _fetch_via_crwl(url, timeout)
            elif b == "jina":
                content = _fetch_via_jina(url, timeout)
            used_backend = b
            break
        except Exception as e:  # noqa: BLE001 — backend-specific exceptions vary
            errors.append(f"{b}: {e}")

    envelope = {
        "url": url,
        "backend": used_backend or None,
        "fetched_at": _now_iso(),
        "content_markdown": content,
        "errors": errors,
    }

    if _should_emit_json(json_out):
        click.echo(_json.dumps(envelope, ensure_ascii=False))
        return

    if not content:
        for e in errors:
            console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    console.print(Panel.fit(
        f"[cyan]{url}[/cyan]\n[dim]backend: {used_backend} · fetched: {envelope['fetched_at']} · {len(content)} chars[/dim]",
        title="omnireach fetch",
    ))
    preview = content[:5000]
    if len(content) > 5000:
        preview += "\n\n…(truncated; 用 --json 拿完整内容)"
    console.print(Markdown(preview))
