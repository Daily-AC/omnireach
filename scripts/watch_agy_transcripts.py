#!/usr/bin/env python3
"""Watch new agy transcript events without attaching to its terminal UI."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

INTERESTING_TYPES = {"ERROR_MESSAGE", "PLANNER_RESPONSE", "SEARCH_WEB"}


def transcript_paths(root: Path) -> list[Path]:
    return sorted(
        root.glob("*/.system_generated/logs/transcript_full.jsonl"),
        key=lambda path: path.stat().st_mtime,
    )


def emit(path: Path, line: str) -> None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return
    event_type = event.get("type")
    if event_type not in INTERESTING_TYPES:
        return
    if event_type == "PLANNER_RESPONSE" and not event.get("tool_calls"):
        return
    payload = {
        "conversation_id": path.parents[2].name,
        "step_index": event.get("step_index"),
        "type": event_type,
        "status": event.get("status"),
    }
    for key in ("tool_calls", "content", "error", "error_code"):
        if key in event:
            payload[key] = event[key]
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def watch(root: Path, interval: float) -> None:
    offsets = {path: path.stat().st_size for path in transcript_paths(root)}
    print(
        json.dumps(
            {
                "watching": str(root),
                "existing_transcripts": len(offsets),
                "status": "ready",
            }
        ),
        flush=True,
    )
    while True:
        for path in transcript_paths(root):
            offset = offsets.setdefault(path, 0)
            size = path.stat().st_size
            if size < offset:
                offset = 0
            if size == offset:
                continue
            with path.open("r", encoding="utf-8") as stream:
                stream.seek(offset)
                for line in stream:
                    emit(path, line)
                offsets[path] = stream.tell()
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.home() / ".gemini" / "antigravity-cli" / "brain",
    )
    parser.add_argument("--interval", type=float, default=0.25)
    args = parser.parse_args()
    try:
        watch(args.root.expanduser(), args.interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
