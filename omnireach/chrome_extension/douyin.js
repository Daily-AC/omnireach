(function installDouyinProjection(root) {
  "use strict";

  const MAX_LIMIT = 30;
  const DURATION_RE = /^\d{1,2}:\d{2}(?::\d{2})?$/;
  const COUNT_RE = /^\d+(?:\.\d+)?[万亿]?$/;

  function parseCount(value) {
    if (typeof value !== "string") return 0;
    const compact = value.replace(/[\s,]/g, "");
    const match = compact.match(/^(\d+(?:\.\d+)?)([万亿])?$/);
    if (!match) return 0;
    const number = Number(match[1]);
    if (!Number.isFinite(number)) return 0;
    if (match[2] === "万") return Math.round(number * 10000);
    if (match[2] === "亿") return Math.round(number * 100000000);
    return Math.round(number);
  }

  function normalizeVideoUrl(value) {
    if (typeof value !== "string" || !value) return "";
    let candidate = value;
    if (candidate.startsWith("//")) candidate = `https:${candidate}`;
    if (candidate.startsWith("/")) {
      candidate = `https://www.douyin.com${candidate}`;
    }
    try {
      const parsed = new URL(candidate);
      if (!/(^|\.)douyin\.com$/.test(parsed.hostname)) return "";
      const match = parsed.pathname.match(/^\/video\/(\d+)$/);
      return match ? `https://www.douyin.com/video/${match[1]}` : "";
    } catch {
      return "";
    }
  }

  function isMetadata(text) {
    if (!text) return true;
    if (DURATION_RE.test(text) || COUNT_RE.test(text)) return true;
    if (/^(合集|视频|作者)$/.test(text)) return true;
    if (/^(刚刚|今天|昨天|前天)$/.test(text)) return true;
    if (/^\d+\s*(秒|分钟|小时|天|周|个月|月|年)前$/.test(text)) {
      return true;
    }
    return /^\d{4}[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?$/.test(text);
  }

  function projectCard(card, index) {
    const url = normalizeVideoUrl(card && (card.href || card.url));
    const texts = Array.isArray(card && card.leafTexts)
      ? card.leafTexts.map((item) => String(item || "").trim()).filter(Boolean)
      : [];
    let author = "";
    let likes = 0;
    let desc = "";

    for (let i = 0; i < texts.length; i += 1) {
      const text = texts[i];
      const renderedAuthor = text.match(/^@(.{1,80})$/);
      if (renderedAuthor && !author) {
        author = renderedAuthor[1].trim();
        continue;
      }
      if (text === "@" && !author) {
        author = texts[i + 1] || "";
        continue;
      }
      if (!likes && COUNT_RE.test(text) && !DURATION_RE.test(text)) {
        likes = parseCount(text);
        continue;
      }
      if (text === author || text === "@" || isMetadata(text)) continue;
      if (text.length > desc.length) desc = text;
    }

    if (author && desc.startsWith(`@${author}`)) {
      desc = desc.slice(author.length + 1).trim();
    }
    return {
      rank: index + 1,
      desc,
      author,
      url,
      plays: 0,
      likes,
      comments: 0,
      shares: 0,
    };
  }

  function projectCards(cards, limit) {
    const selected = Array.isArray(cards) ? cards.slice(0, limit) : [];
    const projected = selected.map((card, index) => projectCard(card, index));
    const rows = projected.filter((row) => row.url && row.desc);
    return { rows, invalidCount: projected.length - rows.length };
  }

  function normalizeLimit(raw) {
    const value = raw === undefined || raw === null ? 10 : Number(raw);
    if (!Number.isInteger(value)) {
      throw new Error("limit must be an integer between 1 and 30");
    }
    if (value < 1 || value > MAX_LIMIT) {
      throw new Error("limit must be between 1 and 30");
    }
    return value;
  }

  root.OmnireachDouyin = Object.freeze({
    normalizeLimit,
    normalizeVideoUrl,
    parseCount,
    projectCard,
    projectCards,
  });
})(globalThis);
