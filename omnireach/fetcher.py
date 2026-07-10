"""Terminal-independent URL fetch service and backend implementations."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from omnireach.adapters._opencli import SILENT_BROWSER_ARGS
from omnireach.contract import FetchEnvelope
from omnireach.html_markdown import html_to_markdown

JINA_BASE = "https://r.jina.ai/"
WECHAT_HOSTS = frozenset({"mp.weixin.qq.com"})

CAPTCHA_KEYWORDS = (
    "环境异常",
    "完成验证后即可继续访问",
    "请输入验证码",
    "请完成安全验证",
    "Cloudflare",
    "Just a moment",
    "Checking your browser",
    "此验证码用于确认",
    "不是自动程序",
)

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.8,zh-CN;q=0.7,zh;q=0.6",
}


def _host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def _looks_like_captcha(markdown: str) -> tuple[bool, str | None]:
    if len(markdown) < 200:
        return False, None
    folded = markdown.casefold()
    for keyword in CAPTCHA_KEYWORDS:
        if keyword.casefold() in folded:
            return True, keyword
    return False, None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fetch_via_crwl(url: str, timeout: float) -> str:
    if not shutil.which("crwl"):
        raise RuntimeError("crwl 不在 PATH (跑 `pip install -U crawl4ai && crawl4ai-setup`)")
    proc = subprocess.run(
        ["crwl", url, "-o", "markdown"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        error = proc.stderr.strip()[:300] or f"exit {proc.returncode}"
        raise RuntimeError(f"crwl 失败: {error}")
    if not proc.stdout.strip():
        raise RuntimeError("crwl 返回空内容")
    return proc.stdout


def _fetch_via_http(url: str, timeout: float) -> str:
    try:
        with httpx.Client(
            headers=HTTP_HEADERS,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            response = client.get(url, headers=HTTP_HEADERS)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"http fetch error: {exc}") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"http fetch 返回 {response.status_code}")
    content_type = response.headers.get("content-type", "").lower()
    if "html" in content_type or "<html" in response.text[:500].lower():
        response_url = getattr(response, "url", None)
        base_url = (
            str(response_url)
            if isinstance(response_url, (str, httpx.URL))
            else url
        )
        body = html_to_markdown(response.text, base_url=base_url)
    else:
        body = response.text
    if not body.strip():
        raise RuntimeError("http fetch 返回空内容")
    return body


def _fetch_via_jina(url: str, timeout: float) -> str:
    target = JINA_BASE + url
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(target, headers={"Accept": "text/markdown"})
    except httpx.HTTPError as exc:
        raise RuntimeError(f"jina http error: {exc}") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"jina 返回 {response.status_code}")
    if not response.text.strip():
        raise RuntimeError("jina 返回空内容")
    return response.text


def _fetch_via_opencli_weixin(url: str, timeout: float) -> str:
    if not shutil.which("opencli"):
        raise RuntimeError("opencli 不在 PATH (跑 `npm i -g github:Daily-AC/OpenCLI`)")
    try:
        proc = subprocess.run(
            [
                "opencli",
                "weixin",
                "download",
                "--url",
                url,
                "--stdout",
                "--format",
                "json",
                *SILENT_BROWSER_ARGS,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"opencli weixin download timeout ({timeout}s)") from exc
    if proc.returncode != 0:
        error = proc.stderr.strip()[:300] or f"exit {proc.returncode}"
        raise RuntimeError(f"opencli 失败: {error}")

    output = proc.stdout
    row = None
    if output.strip():
        try:
            parsed = json.loads(output.strip())
            candidate = parsed[0] if isinstance(parsed, list) and parsed else parsed
            if isinstance(candidate, dict) and "status" in candidate:
                row = candidate
        except (ValueError, TypeError):
            pass
    if row is not None:
        status = str(row.get("status", ""))
        if "verification" in status.lower() or "环境异常" in status:
            raise RuntimeError(f"captcha_suspected: {status}")
        raise RuntimeError(f"opencli 失败: {status}")
    if not output.strip():
        raise RuntimeError("opencli 返回空内容")
    return output


def _resolve_backends(url: str, backend: str) -> list[str]:
    if backend != "auto":
        return [backend]
    if _host_of(url) in WECHAT_HOSTS:
        return ["opencli"]
    return ["http", "jina"]


def fetch(
    url: str,
    *,
    backend: str = "auto",
    timeout: float = 30.0,
) -> FetchEnvelope:
    """Fetch a URL through the host-aware backend sequence."""
    backends = {
        "http": _fetch_via_http,
        "jina": _fetch_via_jina,
        "crwl": _fetch_via_crwl,
        "opencli": _fetch_via_opencli_weixin,
    }
    content = ""
    used_backend = None
    errors: list[str] = []
    for name in _resolve_backends(url, backend):
        try:
            candidate = backends[name](url, timeout)
            suspicious, keyword = _looks_like_captcha(candidate)
            if suspicious:
                errors.append(
                    f"{name}: captcha_suspected: response contains "
                    f"verification-page keyword '{keyword}'"
                )
                continue
            content = candidate
            used_backend = name
            break
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")
    return FetchEnvelope(
        url=url,
        backend=used_backend,
        fetched_at=_now_iso(),
        content_markdown=content,
        errors=errors,
    )
