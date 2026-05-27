"""omnireach fetch <url> — get full markdown content from a URL (v0.10).

Backends (dual-backend pattern, same as wechat/bilibili adapters):
- `crwl` (Crawl4AI, local install): preferred, 内置反爬
- `jina` (r.jina.ai SaaS): zero-config fallback, 免费额度大
- `opencli` (v0.10.1+): mp.weixin.qq.com URLs only — OpenCLI weixin download
  cookie-strategy path, bypasses verification-page traps that crwl/jina hit

CLI:
    omnireach fetch <url>                     # auto: host-aware (mp.weixin.qq.com → opencli; else crwl → jina)
    omnireach fetch <url> --backend crwl      # crwl only, fail if not installed
    omnireach fetch <url> --backend jina      # jina only
    omnireach fetch <url> --backend opencli   # opencli only (only meaningful for mp.weixin.qq.com)
    omnireach fetch <url> --json              # explicit JSON output
"""

from __future__ import annotations

import json as _json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import click
import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()

JINA_BASE = "https://r.jina.ai/"

# v0.10.1: hosts that have a dedicated cookie-strategy backend.
# mp.weixin.qq.com gets verification-page-trapped by generic web fetchers;
# OpenCLI's `weixin download --stdout` uses a logged-in Chrome profile and
# bypasses this.
WECHAT_HOSTS = frozenset({"mp.weixin.qq.com"})

# v0.10.1: CAPTCHA / verification-gate keyword heuristic. Used to flag
# crwl/jina responses that look like verification pages instead of real
# article content. OpenCLI path doesn't need these — it surfaces a
# structured `status: 'failed — verification required'` row directly.
CAPTCHA_KEYWORDS = (
    "环境异常",
    "完成验证后即可继续访问",
    "请输入验证码",
    "请完成安全验证",
    "Cloudflare",
    "Just a moment",
    "Checking your browser",
)


def _host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001 — urlparse rarely fails but be safe
        return ""


def _looks_like_captcha(markdown: str) -> tuple[bool, str | None]:
    """Heuristic: does this markdown look like a verification/CAPTCHA page?

    Returns (suspicious, matched_keyword). Only flips True for non-trivial
    payloads (< 200 chars is too short to be a real article anyway, but is
    also too short for keyword matching to be meaningful — leave that to the
    "empty content" path).
    """
    if len(markdown) < 200:
        return False, None
    for kw in CAPTCHA_KEYWORDS:
        if kw in markdown:
            return True, kw
    return False, None


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


def _fetch_via_opencli_weixin(url: str, timeout: float) -> str:
    """Invoke `opencli weixin download --url <url> --stdout --format json`.

    Output disambiguation (3 branches), per spec §7.1:
      1. retcode != 0  → opencli_failed (raise; stderr surfaced)
      2. retcode == 0 + stdout parses as JSON with a 'status' field → row-level
         status path; check 'verification' keyword to split captcha_suspected
         (raise with captcha_suspected:... prefix) vs opencli_failed
      3. retcode == 0 + stdout is NOT valid JSON (or has no 'status' field)
         → real markdown body, possibly starting with '[作者按]' etc.
    """
    if not shutil.which("opencli"):
        raise RuntimeError("opencli 不在 PATH (跑 `npm i -g github:Daily-AC/OpenCLI`)")
    try:
        proc = subprocess.run(
            ["opencli", "weixin", "download", "--url", url, "--stdout", "--format", "json"],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"opencli weixin download timeout ({timeout}s)") from e
    # Branch 1: binary-level failure
    if proc.returncode != 0:
        err = proc.stderr.strip()[:300] or f"exit {proc.returncode}"
        raise RuntimeError(f"opencli 失败: {err}")
    out = proc.stdout
    # Branch 2: try-parse as JSON row (errorHint or row-level status)
    row = None
    stripped = out.strip()
    if stripped:
        try:
            parsed = _json.loads(stripped)
            candidate = parsed[0] if isinstance(parsed, list) and parsed else parsed
            if isinstance(candidate, dict) and "status" in candidate:
                row = candidate
        except (ValueError, TypeError):
            row = None
    if row is not None:
        status = str(row.get("status", ""))
        if "verification" in status.lower() or "环境异常" in status:
            raise RuntimeError(f"captcha_suspected: {status}")
        raise RuntimeError(f"opencli 失败: {status}")
    # Branch 3: plain markdown body (success)
    if not out.strip():
        raise RuntimeError("opencli 返回空内容")
    return out


def _resolve_backends(url: str, backend: str) -> list[str]:
    """Decide which backend(s) to try.

    Rules (per spec §11 Q2 ack):
    - Explicit `--backend X` always wins, user's choice respected.
    - `--backend auto` + host in WECHAT_HOSTS → opencli only (single attempt;
      no jina/crwl fallback because they'd just hit the verification page
      we're trying to avoid).
    - `--backend auto` + other hosts → crwl → jina (preserved v0.10 behavior).
    """
    if backend != "auto":
        return [backend]
    if _host_of(url) in WECHAT_HOSTS:
        return ["opencli"]
    return ["crwl", "jina"]


@click.command("fetch")
@click.argument("url")
@click.option("--backend", type=click.Choice(["auto", "crwl", "jina", "opencli"]), default="auto",
              help="auto = host-aware (mp.weixin.qq.com → opencli; else crwl → jina); 或显式指定")
@click.option("--json", "json_out", is_flag=True, help="输出 JSON envelope, 适合下游 pipe")
@click.option("--timeout", type=float, default=30.0, help="单 backend 超时秒数")
def fetch_cmd(url: str, backend: str, json_out: bool, timeout: float) -> None:
    """获取 URL 的全文 markdown.

    omnireach search 返 metadata + URL; omnireach fetch 把 URL 变成全文 markdown.
    Default `auto`: mp.weixin.qq.com URLs 走 OpenCLI 登录态 Chrome
    (`opencli weixin download --stdout`); 其它 URLs 走 crwl (Crawl4AI, 本地) 优先,
    失败或没装走 jina (r.jina.ai SaaS) fallback.

    示例:
        omnireach fetch https://mp.weixin.qq.com/s/abc      # 自动走 opencli
        omnireach fetch https://example.com/article         # 自动走 crwl → jina
        omnireach search --on wechat "claude" --json | \\
            jq -r '.results[].url' | xargs -I{} omnireach fetch {} --json
    """
    backends_to_try = _resolve_backends(url, backend)
    content = ""
    used_backend = ""
    errors: list[str] = []
    captcha_warning: str | None = None

    for b in backends_to_try:
        try:
            if b == "crwl":
                content = _fetch_via_crwl(url, timeout)
            elif b == "jina":
                content = _fetch_via_jina(url, timeout)
            elif b == "opencli":
                content = _fetch_via_opencli_weixin(url, timeout)
            used_backend = b
            break
        except Exception as e:  # noqa: BLE001 — backend-specific exceptions vary
            errors.append(f"{b}: {e}")

    # v0.10.1: CAPTCHA heuristic for crwl/jina paths. The opencli backend
    # surfaces a structured row directly via captcha_suspected: prefix in
    # the RuntimeError message (already captured in errors above), so we
    # only need post-hoc keyword scan for non-opencli successful returns.
    if content and used_backend in ("crwl", "jina"):
        suspicious, kw = _looks_like_captcha(content)
        if suspicious:
            captcha_warning = (
                f"captcha_suspected: {used_backend} returned content containing "
                f"verification-page keyword '{kw}'; consider --backend opencli for "
                f"mp.weixin.qq.com or check the URL in a browser"
            )
            errors.append(captcha_warning)

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
