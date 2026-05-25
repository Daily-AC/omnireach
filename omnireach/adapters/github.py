"""GitHub adapter — shells out to `gh search`."""

from __future__ import annotations

import asyncio
import json
import shutil

from omnireach.adapters.base import AdapterBase, AdapterUnavailable
from omnireach.contract import SearchResult


class GitHubAdapter(AdapterBase):
    name = "github"
    requires = ["gh"]

    async def is_ready(self) -> bool:
        return shutil.which("gh") is not None

    async def _run(self, *args: str) -> list[dict]:
        proc = await asyncio.create_subprocess_exec(
            "gh", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("github", stderr.decode().strip() or "gh failed")
        try:
            return json.loads(stdout.decode() or "[]")
        except json.JSONDecodeError:
            return []

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("gh"):
            raise AdapterUnavailable("github", "gh CLI not installed",
                                     hint="omnireach setup github")
        half = max(1, limit // 2)
        repo_fields = "fullName,url,description,stargazersCount,updatedAt"
        issue_fields = "title,url,body,author,createdAt"
        repos, issues = await asyncio.gather(
            self._run("search", "repos", query, "--json", repo_fields, "--limit", str(half)),
            self._run("search", "issues", query, "--json", issue_fields, "--limit", str(half)),
            return_exceptions=True,
        )
        results: list[SearchResult] = []
        if isinstance(repos, list):
            for r in repos:
                results.append(SearchResult(
                    source="github", adapter="gh",
                    title=r.get("fullName") or "",
                    url=r.get("url") or "",
                    content=r.get("description") or "",
                    ts=r.get("updatedAt"),
                    raw=r,
                ))
        if isinstance(issues, list):
            for i in issues:
                results.append(SearchResult(
                    source="github", adapter="gh",
                    title=i.get("title") or "",
                    url=i.get("url") or "",
                    content=(i.get("body") or "")[:500],
                    author=(i.get("author") or {}).get("login"),
                    ts=i.get("createdAt"),
                    raw=i,
                ))
        return results
