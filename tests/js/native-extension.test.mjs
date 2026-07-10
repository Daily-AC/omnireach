import assert from "node:assert/strict";
import { test } from "node:test";

await import("../../omnireach/chrome_extension/douyin.js");

const douyin = globalThis.OmnireachDouyin;

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
