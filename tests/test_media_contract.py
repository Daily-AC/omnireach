import pytest
from pydantic import ValidationError

from omnireach.media.contract import MediaArtifact, MediaEnvelope


def test_media_envelope_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        MediaEnvelope(
            ok=True,
            url="https://example.com/video.mp4",
            source="direct",
            media_type="video",
            mode="inspect",
            parsed_at="2026-07-22T00:00:00Z",
            leaked_signed_url="https://secret.example/token",
        )


def test_media_artifact_requires_absolute_shape_and_checksum():
    artifact = MediaArtifact(
        kind="metadata",
        path="/tmp/metadata.json",
        mime="application/json",
        bytes=2,
        sha256="a" * 64,
    )

    assert artifact.path == "/tmp/metadata.json"
    with pytest.raises(ValidationError):
        MediaArtifact(
            kind="metadata",
            path="/tmp/metadata.json",
            mime="application/json",
            bytes=2,
            sha256="not-a-checksum",
        )
    with pytest.raises(ValidationError):
        MediaArtifact(
            kind="metadata",
            path="metadata.json",
            mime="application/json",
            bytes=2,
            sha256="a" * 64,
        )
