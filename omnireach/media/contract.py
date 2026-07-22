"""Stable JSON contract for media inspection and parsing."""

from __future__ import annotations

from typing import Literal

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DESCRIPTION_MAX = 10000


class MediaError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: Literal["resolve", "inspect", "subtitle", "artifact"]
    backend: str
    category: Literal["unavailable", "failed", "blocked", "limit", "invalid"]
    message: str
    hint: str = ""
    retryable: bool = False


class MediaArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["metadata", "subtitle", "transcript_json", "transcript_markdown", "manifest"]
    path: str = Field(description="Absolute local filesystem path")
    mime: str
    bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("path")
    @classmethod
    def _absolute_path(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("artifact path must be absolute")
        return value


class MediaTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["subtitle"] = "subtitle"
    language: str
    format: str
    source: Literal["publisher", "automatic", "sidecar"]


class MediaMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    title: str | None = None
    author: str | None = None
    description: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    published_at: str | None = None
    thumbnail_url: str | None = None
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    codec: str | None = None

    @field_validator("description")
    @classmethod
    def _bounded_description(cls, value: str | None) -> str | None:
        if value is None or len(value) <= _DESCRIPTION_MAX:
            return value
        return value[:_DESCRIPTION_MAX]


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str


class MediaTranscript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str
    source: Literal["publisher", "automatic", "sidecar"]
    segment_count: int = Field(ge=0)
    text_preview: str
    truncated: bool


class MediaProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    tool_version: str | None = None
    inspected_at: str


class MediaEnvelope(BaseModel):
    """Top-level result returned by media inspect and quick parse."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    url: str
    source: str
    media_type: Literal["video", "audio", "unknown"]
    backend: Literal["direct", "yt-dlp", "bilibili-api"] | None = None
    mode: Literal["inspect", "quick"]
    parsed_at: str
    metadata: MediaMetadata | None = None
    tracks: list[MediaTrack] = Field(default_factory=list)
    artifacts: list[MediaArtifact] = Field(default_factory=list)
    transcript: MediaTranscript | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[MediaError] = Field(default_factory=list)
    provenance: list[MediaProvenance] = Field(default_factory=list)
