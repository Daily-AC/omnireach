import assert from "node:assert/strict";
import { test } from "node:test";

await import("../../omnireach/chrome_extension/douyin.js");
await import("../../omnireach/chrome_extension/sites.js");

const douyin = globalThis.OmnireachDouyin;
const sites = globalThis.OmnireachSites;

test("parses Douyin display counts", () => {
  assert.equal(douyin.parseCount("4702"), 4702);
  assert.equal(douyin.parseCount("1.9万"), 19000);
  assert.equal(douyin.parseCount("1.2亿"), 120000000);
  assert.equal(douyin.parseCount("not-a-count"), 0);
});

test("normalizes only canonical Douyin video URLs", () => {
  assert.equal(
    douyin.normalizeVideoUrl("/video/7660676358325980435"),
    "https://www.douyin.com/video/7660676358325980435",
  );
  assert.equal(
    douyin.normalizeVideoUrl("https://www.douyin.com/video/7660678247994248498"),
    "https://www.douyin.com/video/7660678247994248498",
  );
  assert.equal(
    douyin.normalizeVideoUrl("https://evil.example/video/7660678247994248498"),
    "",
  );
});

test("projects a serialized result card", () => {
  const row = douyin.projectCard(
    {
      href: "/video/7660676358325980435",
      leafTexts: [
        "01:23",
        "1.9万",
        "@",
        "程序员阿江",
        "今天",
        "GPT-5.6 SOL 真顶，我拿真实开源项目测完了",
      ],
    },
    0,
  );

  assert.deepEqual(row, {
    rank: 1,
    desc: "GPT-5.6 SOL 真顶，我拿真实开源项目测完了",
    author: "程序员阿江",
    url: "https://www.douyin.com/video/7660676358325980435",
    plays: 0,
    likes: 19000,
    comments: 0,
    shares: 0,
  });
});

test("projects the real rendered Douyin anchor text shape", () => {
  const row = douyin.projectCard(
    {
      href: "//www.douyin.com/video/7660676358325980435",
      leafTexts: [
        "合集",
        "05:55",
        "1326",
        "GPT-5.6 SOL 真顶｜我拿真实开源项目测完了",
        "@程序员阿江-Relakkes",
        "17小时前",
      ],
    },
    0,
  );

  assert.equal(row.desc, "GPT-5.6 SOL 真顶｜我拿真实开源项目测完了");
  assert.equal(row.author, "程序员阿江-Relakkes");
  assert.equal(row.likes, 1326);
  assert.equal(
    row.url,
    "https://www.douyin.com/video/7660676358325980435",
  );
});

test("reports malformed cards instead of silently dropping them", () => {
  const projected = douyin.projectCards(
    [
      { href: "/video/1", leafTexts: ["valid description"] },
      { href: "", leafTexts: ["missing URL"] },
    ],
    2,
  );

  assert.equal(projected.rows.length, 1);
  assert.equal(projected.invalidCount, 1);
});

test("validates search limit without clamping", () => {
  assert.equal(douyin.normalizeLimit(10), 10);
  assert.throws(() => douyin.normalizeLimit(0), /between 1 and 30/);
  assert.throws(() => douyin.normalizeLimit(31), /between 1 and 30/);
  assert.throws(() => douyin.normalizeLimit("1.5"), /integer/);
});

test("projects the real Google search shape", () => {
  const projected = sites.projectGoogle(
    [
      {
        snippet: "Python 3.14.0 is the newest major release.",
        title: "Python Release Python 3.14.0",
        type: "result",
        url: "https://www.python.org/downloads/release/python-3140/",
      },
    ],
    3,
  );

  assert.equal(projected.invalidCount, 0);
  assert.equal(projected.rows[0].type, "result");
  assert.match(projected.rows[0].url, /^https:\/\/www\.python\.org\//);
});

test("projects the real Reddit JSON shape and rejects verification HTML", () => {
  const projected = sites.projectReddit(
    [
      {
        id: "abc",
        title: "Python 3.14",
        author: "reader",
        score: 561,
        comments: 169,
        url: "https://www.reddit.com/r/Python/comments/abc/python_314/",
        created_utc: 1781529030,
        selftext: "Details",
      },
      { title: "Reddit - Please wait for verification", url: "" },
    ],
    3,
  );

  assert.equal(projected.rows.length, 1);
  assert.equal(projected.invalidCount, 1);
  assert.equal(projected.rows[0].score, 561);
});

test("projects real TikTok API fields", () => {
  const projected = sites.projectTikTok(
    [
      {
        author: "dev",
        desc: "Python coding tutorial",
        likes: 8400,
        plays: 120000,
        comments: 312,
        shares: 540,
        url: "https://www.tiktok.com/@dev/video/7234",
      },
    ],
    3,
  );

  assert.deepEqual(projected.rows[0], {
    rank: 1,
    desc: "Python coding tutorial",
    author: "dev",
    url: "https://www.tiktok.com/@dev/video/7234",
    plays: 120000,
    likes: 8400,
    comments: 312,
    shares: 540,
  });
});

test("normalizes Xiaohongshu note rows and derives the date", () => {
  const projected = sites.projectXiaohongshu(
    [
      {
        title: "Python 3.14 changes",
        author: "AI dev 3天前",
        likes: "1.2万",
        url: "https://www.xiaohongshu.com/explore/697f6c740000000000000000",
      },
    ],
    3,
  );

  assert.equal(projected.rows[0].published_at, "2026-02-01");
  assert.equal(projected.rows[0].author, "AI dev");
  assert.equal(projected.rows[0].likes, "1.2万");
});

test("normalizes Twitter DOM counters and canonical status rows", () => {
  const projected = sites.projectTwitter(
    [
      {
        text: "Python 3.14 is out",
        author: "python",
        likes: "1.2K",
        retweets: "42",
        replies: "7",
        views: "56.7K",
        url: "https://x.com/python/status/123456",
      },
    ],
    3,
  );

  assert.equal(projected.rows[0].id, "123456");
  assert.equal(projected.rows[0].likes, 1200);
  assert.equal(projected.rows[0].views, 56700);
});

test("shared site limits are strict", () => {
  assert.equal(sites.normalizeLimit(10), 10);
  assert.throws(() => sites.normalizeLimit(0), /between 1 and 30/);
  assert.throws(() => sites.normalizeLimit(31), /between 1 and 30/);
});

// The trimmed item shape below mirrors a real `aweme/v1/web/aweme/post/`
// response captured from a logged-in session on 2026-09-03.
const AWEME = {
  aweme_id: "7267478481213181238",
  desc: "把东方美学带到欧洲 #卢浮宫 #马面裙",
  create_time: 1692091704,
  duration: 25843,
  media_type: 4,
  statistics: {
    digg_count: 6534100,
    comment_count: 127865,
    share_count: 473803,
    collect_count: 252270,
    play_count: 0,
  },
  author: { nickname: "彭十六elf", sec_uid: "MS4wLjABAAAAAAKy2_R6k-oFWT5E-97gbGZQ1laaweQMWImJDkDaef0" },
  music: "@彭十六elf创作的原声",
  hashtags: ["卢浮宫", "马面裙"],
  video_tags: ["随拍", "人物随拍", "人物图片轮播"],
};

test("projects one catalog item with exact counters", () => {
  assert.deepEqual(douyin.projectAweme(AWEME, 0), {
    rank: 1,
    aweme_id: "7267478481213181238",
    desc: "把东方美学带到欧洲 #卢浮宫 #马面裙",
    url: "https://www.douyin.com/video/7267478481213181238",
    author: "彭十六elf",
    sec_uid: "MS4wLjABAAAAAAKy2_R6k-oFWT5E-97gbGZQ1laaweQMWImJDkDaef0",
    created_at: "2023-08-15T09:28:24.000Z",
    duration_ms: 25843,
    media_type: "video",
    likes: 6534100,
    comments: 127865,
    shares: 473803,
    collects: 252270,
    plays: 0,
    music: "@彭十六elf创作的原声",
    hashtags: ["卢浮宫", "马面裙"],
    video_tags: ["随拍", "人物随拍", "人物图片轮播"],
    pinned: false,
  });
});

test("marks pinned works and sorts them back into real chronology", () => {
  // Measured 2026-09-03: Douyin hoists is_top works to positions 0-2 and only
  // the remainder is reverse-chronological, so a raw "recent" answer would open
  // with a 2023 video above a 2026 one.
  const pinnedOld = { ...AWEME, aweme_id: "1", is_top: 1, create_time: 1692091704 };
  const freshest = { ...AWEME, aweme_id: "2", create_time: 1767916800 };
  const older = { ...AWEME, aweme_id: "3", create_time: 1735689600 };

  assert.equal(douyin.projectAweme(pinnedOld, 0).pinned, true);

  const recent = douyin.projectAwemeList([pinnedOld, freshest, older], 3, "recent");
  assert.deepEqual(recent.rows.map((row) => row.aweme_id), ["2", "3", "1"]);
  assert.deepEqual(recent.rows.map((row) => row.rank), [1, 2, 3]);
});

test("labels photo posts and keeps the playback URL opt-in", () => {
  const photo = douyin.projectAweme({ ...AWEME, media_type: 2 }, 0);
  assert.equal(photo.media_type, "image");
  assert.equal("play_url" in photo, false);

  const withUrl = douyin.projectAweme(
    { ...AWEME, play_url: "https://v26-web.douyinvod.com/x?a=6383" },
    0,
  );
  assert.equal(withUrl.play_url, "https://v26-web.douyinvod.com/x?a=6383");
});

test("drops catalog items without a usable video id", () => {
  assert.equal(douyin.projectAweme({ ...AWEME, aweme_id: "" }, 0), null);
  assert.equal(douyin.projectAweme(null, 0), null);
});

test("orders a catalog by likes and renumbers ranks", () => {
  const items = [
    { ...AWEME, aweme_id: "1", statistics: { ...AWEME.statistics, digg_count: 10 } },
    { ...AWEME, aweme_id: "2", statistics: { ...AWEME.statistics, digg_count: 30 } },
    { ...AWEME, aweme_id: "3", statistics: { ...AWEME.statistics, digg_count: 20 } },
  ];

  const recent = douyin.projectAwemeList(items, 3, "recent");
  assert.equal(recent.rows.length, 3);

  const liked = douyin.projectAwemeList(items, 2, "likes");
  assert.deepEqual(liked.rows.map((row) => row.aweme_id), ["2", "3"]);
  assert.deepEqual(liked.rows.map((row) => row.rank), [1, 2]);
  assert.equal(liked.scanned, 3);
});

test("de-duplicates repeated catalog pages before applying the limit", () => {
  const items = [AWEME, AWEME, { ...AWEME, aweme_id: "9" }];
  const projected = douyin.projectAwemeList(items, 10, "recent");

  assert.equal(projected.rows.length, 2);
  assert.equal(projected.scanned, 2);
});

test("reads a sec_uid out of a profile URL or a bare id", () => {
  const sec = "MS4wLjABAAAAAAKy2_R6k-oFWT5E-97gbGZQ1laaweQMWImJDkDaef0";
  assert.equal(douyin.secUidFromInput(`https://www.douyin.com/user/${sec}`), sec);
  assert.equal(douyin.secUidFromInput(`https://www.douyin.com/user/${sec}?from=x`), sec);
  assert.equal(douyin.secUidFromInput(sec), sec);
  assert.equal(douyin.secUidFromInput("彭十六"), "");
  assert.equal(douyin.secUidFromInput("https://www.douyin.com/user/self"), "");
  assert.equal(douyin.secUidFromInput(`https://evil.example/user/${sec}`), "");
});

test("picks the real account out of identically named impersonators", () => {
  // Line text is what douyin.com/search?type=user actually renders: the
  // 抖音号, total likes and follower count arrive glued into one string.
  const candidates = [
    { secUid: "self", lines: ["我的"] },
    {
      secUid: "MS4wLjABAAAAreal",
      lines: ["彭十六elf", "认证徽章", "抖音号: elfin1610.6亿获赞2819.5万粉丝"],
    },
    {
      secUid: "MS4wLjABAAAAfake",
      lines: ["彭十六elff", "关注", "抖音号: dydi444aduph76.2万获赞8.8万粉丝"],
    },
    {
      secUid: "MS4wLjABAAAAunrelated",
      lines: ["某个大号", "抖音号: whatever1亿获赞9999.9万粉丝"],
    },
  ];

  const picked = douyin.pickUserCandidate(candidates, "彭十六");
  assert.equal(picked.secUid, "MS4wLjABAAAAreal");
  assert.equal(picked.followers, 28195000);

  assert.equal(douyin.pickUserCandidate([], "彭十六"), null);
  assert.equal(douyin.pickUserCandidate([{ secUid: "self", lines: ["我的"] }], "x"), null);
});

test("refuses to answer a nonsense query with a recommended stranger", () => {
  // Both rows below are real: searching "zzz不存在的创作者zzz9911" on 2026-09-03
  // returned recommendations rather than an empty page, and two earlier rules
  // each answered with one of them — 小非凡追剧 by "pick the most followed", and
  // Zzz by "the query contains the name". Neither is the creator anyone asked
  // for, and a wrong catalog returned confidently is worse than no catalog.
  const candidates = [
    { secUid: "MS4wLjABAAAAbig", lines: ["小非凡追剧", "抖音号: xff1亿获赞472.6万粉丝"] },
    { secUid: "MS4wLjABAAAAzzz", lines: ["Zzz", "抖音号: zzz9200获赞107粉丝"] },
  ];

  assert.equal(douyin.pickUserCandidate(candidates, "zzz不存在的创作者zzz9911"), null);
  assert.deepEqual(
    douyin.userCandidates(candidates).map((row) => row.nickname),
    ["小非凡追剧", "Zzz"],
  );
});

test("matches a query that is longer than the account name", () => {
  const candidates = [{ secUid: "MS4wLjABAAAAx", lines: ["彭十六", "8.8万粉丝"] }];

  assert.equal(douyin.pickUserCandidate(candidates, "彭十六elf").secUid, "MS4wLjABAAAAx");
  // …but only while the name still covers most of the query.
  assert.equal(douyin.pickUserCandidate(candidates, "彭十六elf的高赞跳舞视频合集"), null);
});

test("parses follower counts out of glued profile text", () => {
  assert.equal(douyin.parseFollowerCount("抖音号: elfin1610.6亿获赞2819.5万粉丝"), 28195000);
  assert.equal(douyin.parseFollowerCount("88.5万粉丝"), 885000);
  assert.equal(douyin.parseFollowerCount("no counts here"), 0);
});

test("bounds the catalog limit", () => {
  assert.equal(douyin.normalizeAuthorLimit(undefined), 20);
  assert.equal(douyin.normalizeAuthorLimit(200), 200);
  assert.throws(() => douyin.normalizeAuthorLimit(201), /between 1 and 200/);
  assert.throws(() => douyin.normalizeAuthorLimit(0), /between 1 and 200/);
  assert.throws(() => douyin.normalizeAuthorLimit(1.5), /between 1 and 200/);
});
