# Douyin download verification

Verified on 2026-07-22 with `yt-dlp 2026.06.09`, `ffprobe`, the OmniReach CLI,
and the real stdio MCP process.

## Upstream

Test URL: `https://www.douyin.com/video/7664188112177079482`

- `yt-dlp --list-extractors` included `Douyin`.
- Anonymous metadata/download preflight failed with `Fresh cookies (not necessarily
  logged in) are needed`.
- Explicit `--cookies-from-browser "chrome:Profile 1"` returned 28 MP4 formats.
- The sanitized real response shape is retained in
  `tests/fixtures/ytdlp_douyin_sanitized.json`; CDN URLs and duplicate mirrors are removed.

## Real download

The bounded CLI command used `quality=small`, a 20 MiB limit, and a dedicated output
directory. It produced:

- `ok=true`, `source=douyin`, `mode=download`, `backend=yt-dlp`
- yt-dlp format `bytevc1_540p_229197-0`
- MP4 size: `6,197,443` bytes
- SHA-256: `4c2eb7ae15566b0c20a1f898c38dce5c8d22524e6d66f0ab04f2d34767516654`
- `ffprobe`: 216.317 seconds, 576x768 HEVC video, AAC audio

The same request reused the manifest only after byte-count and SHA-256 checks and returned
`cache_hit=true`. A recursive manifest scan found no browser profile, cookie, token,
`x-signature`, or `x-expires` value. The signed Douyin thumbnail was omitted from public
metadata and reported through a value-free warning.

## Real error boundaries

- The same CLI call without browser cookies returned `category=blocked`, an explicit
  `--cookies-from-browser` recovery hint, no artifacts, and process exit code 1.
- A 5 MiB limit returned `category=limit` before download because the smallest reported
  MP4 was 6,197,443 bytes; process exit code was 1.
- A real `omnireach_download_media` stdio MCP call returned `isError=false` and the same
  media byte count and SHA-256 from an OmniReach-managed directory.
