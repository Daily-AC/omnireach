"""Doctor — per-source readiness check + fetch-backend probe."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

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
    """v0.9.3: external fetch tool that complements omnireach's search layer.

    omnireach returns metadata + URL only. To get full article content from
    those URLs, users pipe into a fetch tool (currently Crawl4AI's `crwl`).
    Doctor reports presence/absence so Agents know whether the full-content
    pipeline is wired.
    """

    tool: str
    ok: bool
    detail: str
    fix_hint: str = ""


@dataclass
class WechatBackendStatus:
    """v0.10.1: host-specific cookie-strategy backend for mp.weixin.qq.com.

    Generic web fetchers (crwl, jina) get verification-page-trapped on
    WeChat article URLs. OpenCLI's `weixin download --stdout` uses the
    user's logged-in Chrome profile to bypass this. Doctor reports whether
    OpenCLI is on PATH AND whether the `--stdout` flag is available
    (M2 added it; older OpenCLI builds may not have it).
    """

    tool: str
    ok: bool
    detail: str
    fix_hint: str = ""


# v0.9.3: known fetch backends — currently just crwl, but designed for growth
# (jina via curl, firecrawl, etc. could be added later).
FETCH_BACKENDS = [
    {
        "tool": "crwl",
        "purpose": "Crawl4AI — URL → 干净 Markdown (反爬绕 Cloudflare/Akamai 等)",
        "fix_hint": "pip install -U crawl4ai && crawl4ai-setup",
    },
]


def run_fetch_backend_doctor() -> list[FetchBackendStatus]:
    """Probe each known fetch backend (binary on PATH)."""
    out: list[FetchBackendStatus] = []
    for b in FETCH_BACKENDS:
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
    out.append(WechatBackendStatus(
        tool="opencli weixin", ok=True,
        detail=f"{purpose} — opencli + `weixin download --stdout` 在 PATH",
    ))
    return out


BINARY_FOR_SOURCE = {
    "youtube": "yt-dlp",
    "github": "gh",
    "reddit": "rdt-cli",
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


async def run_doctor() -> list[SourceStatus]:
    reg = load_registry()
    statuses: list[SourceStatus] = []
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
        if sid in ("twitter", "xiaohongshu", "tiktok", "douyin"):
            # v0.3 OpenCLI path — check for OpenCLI binary
            for candidate in ("openrouter", "opencli", "opencli-search"):
                if shutil.which(candidate):
                    statuses.append(SourceStatus(sid, spec.tier, ok=True,
                        detail=f"{candidate} 在 PATH"))
                    break
            else:
                statuses.append(SourceStatus(sid, spec.tier, ok=False,
                    detail="OpenCLI 不在 PATH",
                    fix_hint=f"omnireach setup {sid}"))
            continue
        statuses.append(SourceStatus(sid, spec.tier, ok=False,
            detail="未实现", fix_hint=""))
    return statuses
