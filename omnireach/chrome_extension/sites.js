(function installSiteProjections(root) {
  "use strict";

  const MAX_LIMIT = 30;

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

  function cleanText(value) {
    return typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";
  }

  function parseCompactCount(value) {
    if (typeof value === "number") {
      return Number.isFinite(value) ? Math.round(value) : 0;
    }
    const compact = cleanText(String(value || "")).replace(/,/g, "").toLowerCase();
    const match = compact.match(/^(\d+(?:\.\d+)?)\s*([kmb]|万|亿)?\+?$/);
    if (!match) return 0;
    const multiplier = {
      "": 1,
      k: 1000,
      m: 1000000,
      b: 1000000000,
      万: 10000,
      亿: 100000000,
    }[match[2] || ""];
    return Math.round(Number(match[1]) * multiplier);
  }

  function validUrl(value, hosts, pathPattern) {
    if (typeof value !== "string" || !value) return "";
    try {
      const parsed = new URL(value);
      if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return "";
      if (hosts.length > 0 && !hosts.some((host) => parsed.hostname === host || parsed.hostname.endsWith(`.${host}`))) {
        return "";
      }
      if (pathPattern && !pathPattern.test(parsed.pathname)) return "";
      return parsed.href;
    } catch {
      return "";
    }
  }

  function projectRows(rows, limit, projector) {
    const projected = (Array.isArray(rows) ? rows : [])
      .slice(0, limit)
      .map(projector);
    const valid = projected.filter(Boolean);
    return { rows: valid, invalidCount: projected.length - valid.length };
  }

  function projectGoogle(rows, limit) {
    return projectRows(rows, limit, (row) => {
      const url = validUrl(row && row.url, [], null);
      const title = cleanText(row && row.title);
      if (!url || !title) return null;
      return {
        type: cleanText(row.type) || "result",
        title,
        url,
        snippet: cleanText(row.snippet).slice(0, 500),
      };
    });
  }

  function projectReddit(rows, limit) {
    return projectRows(rows, limit, (row) => {
      const url = validUrl(row && row.url, ["reddit.com"], /\/comments\//);
      const title = cleanText(row && row.title);
      if (!url || !title) return null;
      return {
        id: cleanText(row.id),
        title,
        subreddit: cleanText(row.subreddit),
        author: cleanText(row.author),
        score: parseCompactCount(row.score),
        comments: parseCompactCount(row.comments),
        url,
        created_utc: Number(row.created_utc) || 0,
        selftext: typeof row.selftext === "string" ? row.selftext : "",
        post_hint: cleanText(row.post_hint),
        url_overridden_by_dest: cleanText(row.url_overridden_by_dest),
        preview_image_url: cleanText(row.preview_image_url),
        gallery_urls: Array.isArray(row.gallery_urls) ? row.gallery_urls : [],
      };
    });
  }

  function projectTikTok(rows, limit) {
    return projectRows(rows, limit, (row, index) => {
      const url = validUrl(row && row.url, ["tiktok.com"], /\/@[^/]+\/video\/\d+/);
      const desc = cleanText(row && row.desc);
      if (!url || !desc) return null;
      return {
        rank: index + 1,
        desc,
        author: cleanText(row.author),
        url,
        plays: parseCompactCount(row.plays),
        likes: parseCompactCount(row.likes),
        comments: parseCompactCount(row.comments),
        shares: parseCompactCount(row.shares),
      };
    });
  }

  function noteIdToDate(url) {
    const match = String(url || "").match(/\/(?:search_result|explore|note)\/([0-9a-f]{24})(?=[?#/]|$)/i);
    if (!match) return "";
    const seconds = Number.parseInt(match[1].slice(0, 8), 16);
    if (seconds < 1000000000 || seconds > 4000000000) return "";
    return new Date((seconds + 8 * 3600) * 1000).toISOString().slice(0, 10);
  }

  function stripXhsAuthorDateSuffix(value) {
    const text = cleanText(value);
    const stripped = text.replace(
      /\s*(?:\d{1,2}天前|\d+小时前|\d+分钟前|\d+秒前|刚刚|昨天|前天|\d+周前|\d+个月前|\d{1,2}-\d{1,2}|\d{4}-\d{1,2}-\d{1,2})$/u,
      "",
    ).trim();
    return stripped || text;
  }

  function projectXiaohongshu(rows, limit) {
    return projectRows(rows, limit, (row, index) => {
      const url = validUrl(
        row && row.url,
        ["xiaohongshu.com"],
        /\/(?:search_result|explore|note)\//,
      );
      const title = cleanText(row && row.title);
      if (!url || !title) return null;
      return {
        rank: index + 1,
        author: stripXhsAuthorDateSuffix(row.author),
        author_url: validUrl(row.author_url, ["xiaohongshu.com"], /\/user\/profile\//),
        likes: cleanText(String(row.likes || "0")),
        title,
        url,
        published_at: cleanText(row.published_at) || noteIdToDate(url),
      };
    });
  }

  function projectTwitter(rows, limit) {
    return projectRows(rows, limit, (row) => {
      const url = validUrl(row && row.url, ["x.com", "twitter.com"], /\/status\/\d+/);
      const text = cleanText(row && row.text);
      if (!url || !text) return null;
      const status = url.match(/\/status\/(\d+)/);
      return {
        id: cleanText(row.id) || (status ? status[1] : ""),
        author: cleanText(row.author),
        bio: cleanText(row.bio),
        text,
        created_at: cleanText(row.created_at),
        replies: parseCompactCount(row.replies),
        retweets: parseCompactCount(row.retweets),
        likes: parseCompactCount(row.likes),
        views: parseCompactCount(row.views),
        url,
        has_media: Boolean(row.has_media),
        media_urls: Array.isArray(row.media_urls) ? row.media_urls : [],
        media_posters: Array.isArray(row.media_posters) ? row.media_posters : [],
        card: row.card && typeof row.card === "object" ? row.card : null,
        quoted_tweet: row.quoted_tweet && typeof row.quoted_tweet === "object" ? row.quoted_tweet : null,
      };
    });
  }

  root.OmnireachSites = Object.freeze({
    normalizeLimit,
    noteIdToDate,
    parseCompactCount,
    projectGoogle,
    projectReddit,
    projectTikTok,
    projectTwitter,
    projectXiaohongshu,
  });
})(globalThis);
