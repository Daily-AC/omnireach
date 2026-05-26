"""Doctor — per-source readiness check."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from omnireach.registry import load_registry


@dataclass
class SourceStatus:
    id: str
    tier: str
    ok: bool
    detail: str
    fix_hint: str = ""


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
    "wechat": "EXA_API_KEY",
    "bilibili": "EXA_API_KEY",
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
