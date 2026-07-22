"""Subtitle normalization without third-party parser dependencies."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from omnireach.media.contract import TranscriptSegment

_TAG_RE = re.compile(r"<[^>]+>")
_VTT_TIMING_RE = re.compile(
    r"(?P<start>(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3})\s+-->\s+"
    r"(?P<end>(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3})"
)


def _timestamp_ms(value: str) -> int:
    parts = value.replace(",", ".").split(":")
    if len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    else:
        hours, minutes, seconds = parts
    return int((int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000)


def _clean_text(value: str) -> str:
    value = _TAG_RE.sub("", value)
    value = html.unescape(value).replace("\u200b", "")
    return " ".join(value.split()).strip()


def parse_vtt_or_srt(content: str) -> list[TranscriptSegment]:
    """Parse common WebVTT/SRT cues and remove adjacent duplicate captions."""
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    segments: list[TranscriptSegment] = []
    index = 0
    while index < len(lines):
        timing = _VTT_TIMING_RE.search(lines[index])
        if not timing:
            index += 1
            continue
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index])
            index += 1
        text = _clean_text(" ".join(text_lines))
        if text and (not segments or segments[-1].text != text):
            segments.append(TranscriptSegment(
                start_ms=_timestamp_ms(timing.group("start")),
                end_ms=_timestamp_ms(timing.group("end")),
                text=text,
            ))
    return segments


def parse_json3(content: str) -> list[TranscriptSegment]:
    """Parse YouTube's json3 subtitle representation."""
    payload = json.loads(content)
    segments: list[TranscriptSegment] = []
    for event in payload.get("events", []):
        chunks = event.get("segs")
        if not isinstance(chunks, list):
            continue
        text = _clean_text("".join(str(chunk.get("utf8", "")) for chunk in chunks))
        if not text:
            continue
        start_ms = max(0, int(event.get("tStartMs") or 0))
        duration_ms = max(0, int(event.get("dDurationMs") or 0))
        if segments and segments[-1].text == text:
            continue
        segments.append(TranscriptSegment(
            start_ms=start_ms,
            end_ms=start_ms + duration_ms,
            text=text,
        ))
    return segments


def parse_bilibili_json(content: str) -> list[TranscriptSegment]:
    """Parse Bilibili's public BCC subtitle JSON."""
    payload = json.loads(content)
    body = payload.get("body")
    if not isinstance(body, list):
        return []
    segments: list[TranscriptSegment] = []
    for cue in body:
        if not isinstance(cue, dict):
            continue
        text = _clean_text(str(cue.get("content") or ""))
        if not text:
            continue
        start_ms = max(0, round(float(cue.get("from") or 0) * 1000))
        end_ms = max(start_ms, round(float(cue.get("to") or 0) * 1000))
        segments.append(TranscriptSegment(
            start_ms=start_ms, end_ms=end_ms, text=text,
        ))
    return segments


def parse_subtitle(content: str, subtitle_format: str) -> list[TranscriptSegment]:
    normalized = subtitle_format.lower().lstrip(".")
    if normalized in {"vtt", "srt"}:
        return parse_vtt_or_srt(content)
    if normalized in {"json", "json3"}:
        payload = json.loads(content)
        if isinstance(payload, dict) and "body" in payload:
            return parse_bilibili_json(content)
        return parse_json3(content)
    raise ValueError(f"unsupported subtitle format: {subtitle_format}")


def transcript_text(segments: list[TranscriptSegment]) -> str:
    return "\n".join(segment.text for segment in segments)


def transcript_markdown(segments: list[TranscriptSegment]) -> str:
    lines = ["# Transcript", ""]
    for segment in segments:
        total_seconds = segment.start_ms // 1000
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        stamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        lines.append(f"- **{stamp}** {segment.text}")
    return "\n".join(lines) + "\n"


def subtitle_format_from_url(url: str, default: str = "vtt") -> str:
    suffix = Path(url.split("?", 1)[0]).suffix.lower().lstrip(".")
    return suffix if suffix in {"vtt", "srt", "json", "json3"} else default
