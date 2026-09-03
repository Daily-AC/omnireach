# Douyin creator catalog verification

Verified on 2026-09-03 against a live logged-in Chrome session, the OmniReach CLI, the
native bridge extension, and the real stdio MCP process. Account under test:
`彭十六elf` (`sec_uid=MS4wLjABAAAAAAKy2_R6k-oFWT5E-97gbGZQ1laaweQMWImJDkDaef0`).

## Why a catalog dimension exists at all

`omnireach search --on douyin --limit 3 "彭十六"` returned three videos, none of them hers:
`大喵喵` (2,278 likes), `大白show` (1,139,000 likes), `抓马娱乐` (26,000 likes). Keyword search
matches captions, so a creator's name mostly returns other accounts' derivative videos, and
ranking those by likes puts a stranger on top.

## Upstream shape

`https://www.douyin.com/aweme/v1/web/aweme/post/` called from the logged-in page context with
`sec_user_id`, `max_cursor`, `count=20`, `aid=6383` needs no `a_bogus`/`X-Bogus` signing and
returns `status_code=0`.

- Per item: `aweme_id`, `desc`, `create_time`, `duration` (ms), `media_type`, `is_top`,
  `statistics.{digg_count,comment_count,share_count,collect_count,play_count}`,
  `author.{nickname,sec_uid}`, `music.title`, `text_extra[].hashtag_name`,
  `video_tag[].tag_name`, `video.play_addr.url_list[0]`.
- `statistics.play_count` is always `0`, so `engagement.views` is reported as unknown.
- `count=20` is a ceiling, not a promise: measured page sizes ran 15, 13, 11, 7, 12, …, 2.
- `media_type=2` marks photo posts; 4 of the 355 works were photo posts.

## Paging

A full scan reached `has_more=0` after **83 pages / 355 works / 35.5 s**, with all 355
`aweme_id` values distinct. The longest run of empty pages inside the catalog was **19**, so
stopping at the first empty page truncates the result — only `has_more=0` terminates.

## Ordering

Douyin hoists pinned works. Measured over the first 140 items: exactly 3 carried `is_top`
and they occupied positions 0, 1 and 2; every remaining item was strictly newest-first. A
raw pass-through therefore opens a "recent" answer with a 2023-08-15 video above a
2026-01-09 one, so `order=recent` sorts by publication date and each result exposes
`raw.pinned`.

## Real runs

| command | result |
|---|---|
| `author <profile URL> --limit 5` | 3.6 s, `scanned=15`, 5 works newest-first from 2026-01-09, `errors=[]` |
| `author "彭十六" --limit 3` | 7.9 s including user resolution, `scanned=15`, `errors=[]` |
| `author "彭十六" --order likes --limit 8 --timeout 300` | 43.6 s, resolved to `彭十六elf` (28,195,000 followers) from search, `scanned=355`, `complete=true`, top work 6,534,099 likes / 127,865 comments |
| `author <profile URL> --limit 1 --include-media-urls` | `raw.play_url` on `v11-weba.douyinvod.com`; `curl` with only a `referer` header returned HTTP 200 and a complete 741,699-byte MP4 — 1080x1920 H.264 + AAC, 9.43 s — with no yt-dlp, no cookies, and no verification challenge |
| `author "zzz不存在的创作者zzz9911"` | exit code 1, no results, one structured error naming the five accounts Douyin offered instead |
| `omnireach_author` over the real stdio MCP process | `isError=false`, and `structuredContent` validated against the declared `AuthorEnvelope` schema |

Before this change, `--limit 5` paged a whole 10-page batch (`scanned=113`, 8.7 s) and
opened with a pinned 2023 video; both are fixed above.

Fetching the catalog needs `world: "MAIN"`. The same request from the default isolated
world was answered `HTTP 403`; dropping the `Referer` from a page-context request changed
nothing, so the rejected extension origin is what matters, not the referer.

## Resolver boundaries

Douyin answers a nonsense user query with recommended accounts rather than an empty page,
so two successive rules each returned a stranger's catalog with no error:

- "pick the most followed candidate" answered `zzz不存在的创作者zzz9911` with `小非凡追剧`
  (4,726,000 followers);
- adding "…or the query contains the account name" answered it with `Zzz` (107 followers).

The shipped rule requires the account name to contain the query, or the query to contain an
account name at least half its length, and returns a structured error listing the candidates
it saw when nothing qualifies. Both real candidate rows are pinned in
`tests/js/native-extension.test.mjs`.
