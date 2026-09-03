"""SearchResult JSON contract — the boundary between omnireach core and adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# v0.8: SERP-snippet rule enforced at the contract boundary. Full upstream
# payloads remain accessible via SearchResult.raw — see
# docs/design/2026-05-27-omnireach-v0.8-design.md.
_SNIPPET_MAX = 500
_ELLIPSIS = "…"


class Engagement(BaseModel):
    model_config = ConfigDict(extra="allow")
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    views: int | None = None


class SearchResult(BaseModel):
    """One normalized hit from one source."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="logical source id, e.g. 'hackernews'")
    adapter: str = Field(description="which adapter produced this, e.g. 'agent-reach'")
    title: str
    url: str
    content: str = ""
    author: str | None = None
    ts: str | None = Field(default=None, description="ISO 8601 publish ts")
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    engagement: Engagement | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    cost: Literal["free", "paid"] = "free"
    raw_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("content")
    @classmethod
    def _truncate_content(cls, v: str) -> str:
        if len(v) <= _SNIPPET_MAX:
            return v
        return v[:_SNIPPET_MAX] + _ELLIPSIS


class SourceError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    error: str
    category: Literal["unavailable", "failed"] = "failed"


class SearchEnvelope(BaseModel):
    """The top-level JSON returned by `omnireach "<query>"`."""

    model_config = ConfigDict(extra="forbid")

    query: str
    ts: str
    results: list[SearchResult] = Field(default_factory=list)
    errors: list[SourceError] = Field(default_factory=list)


class AuthorIdentity(BaseModel):
    """Which account a creator-catalog request actually resolved to."""

    model_config = ConfigDict(extra="forbid")

    source: str
    handle: str = Field(description="what the caller asked for")
    id: str = Field(description="platform-stable creator id, e.g. a Douyin sec_uid")
    name: str = ""
    url: str = ""
    followers: int | None = None
    resolved_from: Literal["url", "search"] = "search"


class AuthorEnvelope(BaseModel):
    """The top-level JSON returned by `omnireach author <handle>`.

    Results reuse `SearchResult` so a catalog is consumable by anything that
    already reads a search envelope; the extra fields say *whose* catalog it
    is and how much of it was actually seen.
    """

    model_config = ConfigDict(extra="forbid")

    query: str
    ts: str
    author: AuthorIdentity | None = None
    order: Literal["recent", "likes"] = "recent"
    scanned: int = Field(default=0, ge=0, description="works seen while paging")
    complete: bool = Field(
        default=False,
        description="whether paging reached the end of the catalog",
    )
    results: list[SearchResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[SourceError] = Field(default_factory=list)


class FetchEnvelope(BaseModel):
    """The top-level JSON returned by `omnireach fetch <url>`."""

    model_config = ConfigDict(extra="forbid")

    url: str
    backend: Literal["http", "jina", "crwl", "opencli"] | None = None
    fetched_at: str
    content_markdown: str = ""
    errors: list[str] = Field(default_factory=list)
