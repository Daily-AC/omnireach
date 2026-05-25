"""SearchResult JSON contract — the boundary between omnireach core and adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
