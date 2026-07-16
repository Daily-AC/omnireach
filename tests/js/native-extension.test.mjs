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
