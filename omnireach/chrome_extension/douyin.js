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

  const MAX_AUTHOR_LIMIT = 200;
  const SEC_UID_RE = /^[A-Za-z0-9_-]{16,120}$/;
  const FOLLOWERS_RE = /([\d.]+[万亿]?)粉丝/;

  function normalizeAuthorLimit(raw) {
    const value = raw === undefined || raw === null ? 20 : Number(raw);
    if (!Number.isInteger(value)) {
      throw new Error("limit must be an integer between 1 and 200");
    }
    if (value < 1 || value > MAX_AUTHOR_LIMIT) {
      throw new Error("limit must be between 1 and 200");
    }
    return value;
  }

  function secUidFromInput(value) {
    const raw = typeof value === "string" ? value.trim() : "";
    if (!raw) return "";
    if (/^https?:\/\//i.test(raw)) {
      try {
        const parsed = new URL(raw);
        if (!/(^|\.)douyin\.com$/.test(parsed.hostname)) return "";
        const match = parsed.pathname.match(/^\/user\/([A-Za-z0-9_-]+)/);
        return match && match[1] !== "self" ? match[1] : "";
      } catch {
        return "";
      }
    }
    // A bare sec_uid is the only non-URL input we can use without a lookup.
    return SEC_UID_RE.test(raw) && raw.startsWith("MS4wLjABAAAA") ? raw : "";
  }

  function parseFollowerCount(text) {
    const match = String(text || "").match(FOLLOWERS_RE);
    return match ? parseCount(match[1]) : 0;
  }

  function userCandidates(candidates) {
    return (Array.isArray(candidates) ? candidates : [])
      .map((candidate) => {
        const secUid = String((candidate && candidate.secUid) || "");
        const lines = Array.isArray(candidate && candidate.lines)
          ? candidate.lines.map((line) => String(line || "").trim()).filter(Boolean)
          : [];
        return {
          secUid,
          nickname: lines[0] || "",
          followers: parseFollowerCount(lines.join(" ")),
        };
      })
      .filter((row) => row.secUid && row.secUid !== "self" && row.nickname)
      .sort((a, b) => b.followers - a.followers);
  }

  function pickUserCandidate(candidates, query) {
    const wanted = String(query || "").trim().toLowerCase();
    if (!wanted) return null;
    // Douyin answers a nonsense query with recommended accounts rather than an
    // empty page, so "take the biggest result" silently returns a stranger's
    // catalog. Only accounts whose name actually relates to the query are
    // eligible; among those, follower count is what separates the real account
    // from the impersonators that copy its name exactly.
    const eligible = userCandidates(candidates).filter((row) => {
      const name = row.nickname.toLowerCase();
      if (name.includes(wanted)) return true;
      // The reverse direction exists so "彭十六elf" still finds an account named
      // "彭十六", but it must not let a three-character recommendation match a
      // long query just by appearing somewhere inside it.
      return wanted.includes(name) && name.length * 2 >= wanted.length;
    });
    if (eligible.length === 0) return null;
    return eligible.reduce((best, row) => (row.followers > best.followers ? row : best));
  }

  function projectAweme(item, index) {
    if (!item || typeof item !== "object") return null;
    const url = normalizeVideoUrl(`/video/${String(item.aweme_id || "")}`);
    if (!url) return null;
    const stats = (item.statistics && typeof item.statistics === "object")
      ? item.statistics
      : {};
    const seconds = Number(item.create_time);
    const durationMs = Number(item.duration);
    const row = {
      rank: index + 1,
      aweme_id: String(item.aweme_id),
      desc: typeof item.desc === "string" ? item.desc : "",
      url,
      author: String((item.author && item.author.nickname) || ""),
      sec_uid: String((item.author && item.author.sec_uid) || ""),
      created_at: Number.isFinite(seconds) && seconds > 0
        ? new Date(seconds * 1000).toISOString()
        : "",
      duration_ms: Number.isFinite(durationMs) && durationMs >= 0
        ? Math.round(durationMs)
        : 0,
      media_type: Number(item.media_type) === 2 ? "image" : "video",
      // Douyin hoists pinned works to the top of the catalog response; keeping
      // the flag lets callers see why a 2023 video precedes a 2026 one.
      pinned: Boolean(item.is_top),
      likes: Number(stats.digg_count) || 0,
      comments: Number(stats.comment_count) || 0,
      shares: Number(stats.share_count) || 0,
      collects: Number(stats.collect_count) || 0,
      // Douyin stopped populating play_count on this endpoint; it is always 0.
      plays: Number(stats.play_count) || 0,
      music: String(item.music || ""),
      hashtags: Array.isArray(item.hashtags)
        ? item.hashtags.map((tag) => String(tag || "")).filter(Boolean)
        : [],
      video_tags: Array.isArray(item.video_tags)
        ? item.video_tags.map((tag) => String(tag || "")).filter(Boolean)
        : [],
    };
    if (typeof item.play_url === "string" && item.play_url) {
      row.play_url = item.play_url;
    }
    return row;
  }

  function projectAwemeList(items, limit, order) {
    const projected = (Array.isArray(items) ? items : []).map(
      (item, index) => projectAweme(item, index),
    );
    const valid = projected.filter(Boolean);
    const seen = new Set();
    const unique = [];
    for (const row of valid) {
      if (seen.has(row.aweme_id)) continue;
      seen.add(row.aweme_id);
      unique.push(row);
    }
    const ordered = orderCatalog(unique, order);
    return {
      rows: ordered.slice(0, limit).map((row, index) => ({ ...row, rank: index + 1 })),
      scanned: unique.length,
      invalidCount: projected.length - valid.length,
    };
  }

  function orderCatalog(rows, order) {
    const copy = Array.isArray(rows) ? rows.slice() : [];
    if (order === "likes") {
      return copy.sort((a, b) => b.likes - a.likes || b.created_at.localeCompare(a.created_at));
    }
    // "recent" means newest first. The API's own order is not that: it hoists
    // pinned works to the front and only the remainder is reverse-chronological
    // (measured 2026-09-03: 3 pinned works at positions 0-2, then strictly
    // descending). Sorting by date puts a pinned 2023 video back below a 2026
    // one instead of letting it masquerade as the newest.
    return copy.sort((a, b) => b.created_at.localeCompare(a.created_at));
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
    normalizeAuthorLimit,
    normalizeLimit,
    normalizeVideoUrl,
    orderCatalog,
    parseCount,
    parseFollowerCount,
    pickUserCandidate,
    projectAweme,
    projectAwemeList,
    projectCard,
    projectCards,
    secUidFromInput,
    userCandidates,
  });
})(globalThis);
