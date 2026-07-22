# Media v0.17 verification

Date: 2026-07-22

This record covers the real upstream checks for the v0.17 media parsing foundation. No
video body was downloaded for the YouTube or Bilibili checks.

## YouTube captions

Command shape:

```bash
omnireach media parse \
  --language en \
  --output-dir /tmp/omnireach-e2e-youtube-cache-v2 \
  --json \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

Observed: `ok=true`, `backend=yt-dlp`, 60 publisher-caption segments, and metadata,
subtitle, transcript JSON, transcript Markdown, and manifest artifacts with absolute paths
and SHA-256 hashes. The public track list was bounded to 40 entries while an explicit
language remained selectable from the full internal list.

## Bilibili captions

The anonymous Bilibili player API reported `need_login_subtitle=true` for
`BV12N4y1M7rh`. After explicitly selecting an authorized local profile:

```bash
omnireach media parse \
  --cookies-from-browser "chrome:Profile 1" \
  --language zh-Hans \
  --output-dir /tmp/omnireach-e2e-bilibili-cache-v2 \
  --json \
  "https://www.bilibili.com/video/BV12N4y1M7rh"
```

Observed: `ok=true`, `backend=yt-dlp`, one inline SRT track, 136 transcript segments, and
all five artifact kinds. Repeating the same command returned `cache_hit=true` without
calling yt-dlp; paths and hashes remained identical.

## Direct media and sidecar captions

Command shape:

```bash
omnireach media parse \
  --subtitle-url "https://raw.githubusercontent.com/web-platform-tests/wpt/3801d935087f3f608ad39fe127e4318507760e3c/media/foo.vtt" \
  --language en \
  --json \
  "https://www.w3schools.com/html/mov_bbb.mp4"
```

Observed: `ok=true`, `backend=direct`, ffprobe metadata for a 10.027 second H.264 video,
one VTT segment, and all five artifact kinds.

## Limits and privacy

- The same 213 second YouTube video with `--max-duration 10` returned a structured
  `category=limit` error and wrote no artifacts.
- Subtitle downloads above 20 MiB are rejected before parsing.
- A recursive scan of all three artifact directories found no browser profile, cookie,
  authorization, signed URL, or token markers.
- Cache entries are accepted only when URL/cache key, path containment, byte count, and
  SHA-256 all match. A tampered subtitle fixture forced a fresh parse in tests.

## Automated and package checks

- `uv run --extra dev pytest -q`: `406 passed in 25.77s`.
- Real stdio `omnireach_parse_media` call returned direct-media metadata successfully.
- `uv build --offline`: built `omnireach-0.17.0a0.tar.gz` and
  `omnireach-0.17.0a0-py3-none-any.whl`.
- The wheel contains the media contract, service, subtitle parser, and CLI module.
