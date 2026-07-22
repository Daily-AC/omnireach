"""Doctor — per-source readiness check + fetch-backend probe."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass

from omnireach.bridge_install import bridge_configured
from omnireach.native_bridge import (
    NativeBridgeCommandError,
    NativeBridgeUnavailable,
    probe_native_bridge,
)
from omnireach.registry import load_registry


@dataclass
class SourceStatus:
    id: str
    tier: str
    ok: bool
    detail: str
    fix_hint: str = ""


@dataclass
class FetchBackendStatus:
    """A built-in or optional backend used by `omnireach fetch`."""

    tool: str
    ok: bool
    detail: str
    fix_hint: str = ""


@dataclass
class MediaBackendStatus:
    """An external binary used by `omnireach media`."""

    tool: str
    ok: bool
    detail: str
    fix_hint: str = ""


@dataclass
class WechatBackendStatus:
    """v0.10.1: host-specific cookie-strategy backend for mp.weixin.qq.com.

    Generic web fetchers (http, crwl, jina) get verification-page-trapped on
    WeChat article URLs. OpenCLI's `weixin download --stdout` uses the
    user's logged-in Chrome profile to bypass this. Doctor reports whether
    OpenCLI is on PATH AND whether the `--stdout` flag is available
    (M2 added it; older OpenCLI builds may not have it).
    """

    tool: str
    ok: bool
    detail: str
    fix_hint: str = ""


@dataclass(frozen=True)
class OpenCLIProbe:
    ok: bool
    detail: str
    fix_hint: str = ""


FETCH_BACKENDS = [
    {
        "tool": "http",
        "purpose": "内置轻量 HTTP + HTML → Markdown (不启动浏览器)",
        "builtin": True,
        "fix_hint": "",
    },
    {
        "tool": "crwl",
        "purpose": "Crawl4AI — 显式 opt-in 的浏览器抓取 backend",
        "builtin": False,
        "fix_hint": "pip install -U crawl4ai && crawl4ai-setup",
    },
]


def run_fetch_backend_doctor() -> list[FetchBackendStatus]:
    """Probe each known fetch backend (binary on PATH)."""
    out: list[FetchBackendStatus] = []
    for b in FETCH_BACKENDS:
        if b.get("builtin"):
            out.append(FetchBackendStatus(
                tool=b["tool"], ok=True, detail=f"{b['purpose']} — 内置可用",
            ))
            continue
        if shutil.which(b["tool"]):
            out.append(FetchBackendStatus(
                tool=b["tool"], ok=True,
                detail=f"{b['purpose']} — 在 PATH",
            ))
        else:
            out.append(FetchBackendStatus(
                tool=b["tool"], ok=False,
                detail=f"{b['purpose']} — 不在 PATH",
                fix_hint=b["fix_hint"],
            ))
    return out


def run_media_backend_doctor() -> list[MediaBackendStatus]:
    """Probe the two binaries used by page and direct-media backends."""
    definitions = (
        ("yt-dlp", "YouTube and supported-page metadata + subtitles", "pip install -U yt-dlp"),
        ("ffprobe", "direct audio/video metadata", "Install ffmpeg (includes ffprobe)"),
        ("ffmpeg", "media conversion for future deep parsing", "Install ffmpeg"),
        (
            "whisper-cli",
            "optional local ASR readiness for future deep parsing",
            "Install whisper.cpp to enable future local ASR",
        ),
    )
    statuses: list[MediaBackendStatus] = []
    for tool, purpose, hint in definitions:
        found = bool(shutil.which(tool))
        statuses.append(MediaBackendStatus(
            tool=tool,
            ok=found,
            detail=f"{purpose} — {'在 PATH' if found else '不在 PATH'}",
            fix_hint="" if found else hint,
        ))
    return statuses


def run_wechat_backend_doctor() -> list[WechatBackendStatus]:
    """v0.10.1: probe OpenCLI + verify it has the `weixin download --stdout` flag.

    Three states:
    - opencli not on PATH → ok=False, install hint
    - opencli on PATH but `weixin download --help` lacks `--stdout` → ok=False,
      fork-update hint (their build is older than Daily-AC fork commit fe28823)
    - opencli on PATH AND `--stdout` present → ok=True
    """
    out: list[WechatBackendStatus] = []
    install_hint = "npm i -g github:Daily-AC/OpenCLI"
    purpose = "OpenCLI weixin download — mp.weixin.qq.com 登录态全文抓取"
    if not shutil.which("opencli"):
        out.append(WechatBackendStatus(
            tool="opencli weixin", ok=False,
            detail=f"{purpose} — opencli 不在 PATH",
            fix_hint=install_hint,
        ))
        return out
    try:
        proc = subprocess.run(
            ["opencli", "weixin", "download", "--help"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        out.append(WechatBackendStatus(
            tool="opencli weixin", ok=False,
            detail=f"{purpose} — `opencli weixin download --help` 未响应",
            fix_hint=install_hint,
        ))
        return out
    help_text = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        out.append(WechatBackendStatus(
            tool="opencli weixin", ok=False,
            detail=f"{purpose} — `weixin download` 子命令不存在",
            fix_hint=install_hint,
        ))
        return out
    if "--stdout" not in help_text:
        out.append(WechatBackendStatus(
            tool="opencli weixin", ok=False,
            detail=f"{purpose} — 缺 `--stdout` flag (build 早于 Daily-AC fork commit fe28823)",
            fix_hint=install_hint,
        ))
        return out
    silent_flags = ("--window", "--site-session", "--keep-tab")
    if any(flag not in help_text for flag in silent_flags):
        out.append(WechatBackendStatus(
            tool="opencli weixin", ok=False,
            detail=(
                f"{purpose} — 当前 OpenCLI 不支持 background ephemeral tab；"
                "升级后才可保证不弹可见标签页"
            ),
            fix_hint=install_hint,
        ))
        return out
    out.append(WechatBackendStatus(
        tool="opencli weixin", ok=True,
        detail=(
            f"{purpose} — --stdout + --window background + ephemeral tab 已支持"
        ),
    ))
    return out


BINARY_FOR_SOURCE = {
    "youtube": "yt-dlp",
    "github": "gh",
}

ENV_FOR_BOOSTER = {
    "tavily": "TAVILY_API_KEY",
    "brave": "BRAVE_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "exa": "EXA_API_KEY",
}

# v0.9: sources that have a free default backend + an optional enhancement
# triggered by an env var (e.g. EXA_API_KEY). The base detail describes the
# free path; if the env var is present, " + <enhanced>" is appended.
FREE_BACKEND_DETAIL = {
    "wechat": "Sogou 免费搜索 (httpx)",
    "bilibili": "B站官方 search API",
}

OPENCLI_SOURCE_IDS = {
    "google", "reddit", "twitter", "xiaohongshu", "tiktok", "douyin"
}

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def run_opencli_doctor() -> OpenCLIProbe:
    """Probe the Browser Bridge connection, not merely the OpenCLI binary."""
    if not shutil.which("opencli"):
        return OpenCLIProbe(
            ok=False,
            detail="OpenCLI 不在 PATH",
            fix_hint="npm i -g github:Daily-AC/OpenCLI",
        )
    try:
        proc = subprocess.run(
            ["opencli", "doctor"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return OpenCLIProbe(
            ok=False,
            detail="`opencli doctor` timeout (>15s)",
            fix_hint="运行 `opencli doctor` 检查 Browser Bridge",
        )
    except OSError as exc:
        return OpenCLIProbe(
            ok=False,
            detail=f"`opencli doctor` 启动失败: {exc}",
            fix_hint="重新安装 OpenCLI",
        )

    output = _ANSI_ESCAPE.sub("", (proc.stdout or "") + (proc.stderr or ""))
    folded = output.casefold()
    if (
        "multiple browser bridge profiles" in folded
        or "no default profile was selected" in folded
    ):
        return OpenCLIProbe(
            ok=False,
            detail="OpenCLI Browser Bridge 多 profile 冲突",
            fix_hint=(
                "运行 `opencli profile list` 后 `opencli profile use <name>`，"
                "或搜索时传 `--profile <name>`"
            ),
        )
    if "[missing] extension" in folded or "[fail] connectivity" in folded:
        return OpenCLIProbe(
            ok=False,
            detail="OpenCLI Browser Bridge 未连接或连通性检查失败",
            fix_hint="打开 Chrome 扩展后运行 `opencli doctor`",
        )
    if proc.returncode != 0:
        last_line = next(
            (line.strip() for line in reversed(output.splitlines()) if line.strip()),
            f"exit {proc.returncode}",
        )
        return OpenCLIProbe(
            ok=False,
            detail=f"`opencli doctor` 失败: {last_line[:200]}",
            fix_hint="运行 `opencli doctor` 查看完整诊断",
        )
    return OpenCLIProbe(ok=True, detail="opencli doctor 通过，Browser Bridge 可用")


def browser_source_status(
    source_id: str,
    tier: str,
    opencli_probe: OpenCLIProbe,
    *,
    native_configured: bool,
    native_details: dict[str, object] | None = None,
    native_error: Exception | None = None,
) -> SourceStatus:
    """Report the shared native-first browser transport and its fallback."""
    if native_configured and native_details is not None:
        version = native_details.get("extensionVersion") or "unknown"
        commands = native_details.get("commands")
        supports_command = (
            f"{source_id}.search" in commands
            if isinstance(commands, list)
            else source_id == "douyin"
        )
        if supports_command:
            return SourceStatus(
                source_id,
                tier,
                ok=True,
                detail=f"原生 Chrome bridge 已连接 (extension {version})",
            )
        native_error = NativeBridgeCommandError(
            f"extension {version} 不支持 {source_id}.search；重新运行 "
            "`omnireach bridge install` 并在 chrome://extensions reload"
        )
    if native_configured and native_error is not None:
        if opencli_probe.ok:
            return SourceStatus(
                source_id,
                tier,
                ok=True,
                detail=f"原生 Chrome bridge 不可用 ({native_error}); OpenCLI fallback 可用",
            )
        return SourceStatus(
            source_id,
            tier,
            ok=False,
            detail=f"原生 Chrome bridge 不可用 ({native_error}); {opencli_probe.detail}",
            fix_hint=(
                "运行 `omnireach bridge status --json`; "
                f"{opencli_probe.fix_hint}"
            ),
        )
    if opencli_probe.ok:
        return SourceStatus(
            source_id, tier, ok=True, detail="OpenCLI fallback 可用"
        )
    return SourceStatus(
        source_id,
        tier,
        ok=False,
        detail=f"原生 Chrome bridge 未安装; {opencli_probe.detail}",
        fix_hint="omnireach bridge install",
    )


def run_douyin_doctor(opencli_probe: OpenCLIProbe) -> SourceStatus:
    """Backward-compatible single-source probe used by existing callers."""
    configured = bridge_configured()
    details: dict[str, object] | None = None
    error: Exception | None = None
    if configured:
        try:
            details = probe_native_bridge()
        except (NativeBridgeUnavailable, NativeBridgeCommandError) as exc:
            error = exc
    return browser_source_status(
        "douyin",
        "heavy",
        opencli_probe,
        native_configured=configured,
        native_details=details,
        native_error=error,
    )


async def run_doctor() -> list[SourceStatus]:
    reg = load_registry()
    statuses: list[SourceStatus] = []
    opencli_probe = (
        run_opencli_doctor()
        if any(spec.id in OPENCLI_SOURCE_IDS for spec in reg.sources)
        else None
    )
    native_configured = bridge_configured()
    native_details: dict[str, object] | None = None
    native_error: Exception | None = None
    if native_configured:
        try:
            native_details = probe_native_bridge()
        except (NativeBridgeUnavailable, NativeBridgeCommandError) as exc:
            native_error = exc
    for spec in reg.sources:
        sid = spec.id
        if spec.tier == "wip":
            statuses.append(SourceStatus(sid, spec.tier, ok=False,
                detail="🚧 v0.6 重写中"))
            continue
        if sid == "hackernews":
            statuses.append(SourceStatus(sid, spec.tier, ok=True,
                detail="HTTP API (Algolia)"))
            continue
        if sid == "rss":
            statuses.append(SourceStatus(sid, spec.tier, ok=True,
                detail="feedparser (内置); 调用形态: omnireach <URL>"))
            continue
        if sid in BINARY_FOR_SOURCE:
            binary = BINARY_FOR_SOURCE[sid]
            if shutil.which(binary):
                statuses.append(SourceStatus(sid, spec.tier, ok=True,
                    detail=f"{binary} 在 PATH"))
            else:
                statuses.append(SourceStatus(sid, spec.tier, ok=False,
                    detail=f"{binary} 不在 PATH",
                    fix_hint=f"omnireach setup {sid}"))
            continue
        if sid in FREE_BACKEND_DETAIL:
            # v0.9: always ok (free backend works); env var is optional enhancement
            base = FREE_BACKEND_DETAIL[sid]
            if spec.enhanced_with and os.environ.get(spec.enhanced_with):
                detail = f"{base} + {spec.enhanced_with} 语义增强"
            elif spec.enhanced_with:
                detail = f"{base} ({spec.enhanced_with} 可选启用增强)"
            else:
                detail = base
            statuses.append(SourceStatus(sid, spec.tier, ok=True, detail=detail))
            continue
        if sid in ENV_FOR_BOOSTER:
            env = ENV_FOR_BOOSTER[sid]
            if os.environ.get(env):
                statuses.append(SourceStatus(sid, spec.tier, ok=True,
                    detail=f"{env} 已配"))
            else:
                statuses.append(SourceStatus(sid, spec.tier, ok=False,
                    detail=f"{env} 未配",
                    fix_hint=f"omnireach setup {sid}"))
            continue
        if sid in OPENCLI_SOURCE_IDS:
            assert opencli_probe is not None
            statuses.append(browser_source_status(
                sid,
                spec.tier,
                opencli_probe,
                native_configured=native_configured,
                native_details=native_details,
                native_error=native_error,
            ))
            continue
        statuses.append(SourceStatus(sid, spec.tier, ok=False,
            detail="未实现", fix_hint=""))
    return statuses
