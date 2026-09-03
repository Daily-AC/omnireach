importScripts("douyin.js", "sites.js");

const OFFSCREEN_DOCUMENT = "offscreen.html";
const EXTENSION_VERSION = "0.3.4";
// A full creator catalog is fetched in batches so that every `executeScript`
// round trip resets the MV3 service-worker idle timer; 83 pages / 355 works
// measured at ~0.5s per page.
const AUTHOR_PAGES_PER_BATCH = 10;
const AUTHOR_MAX_PAGES = 400;
const AUTHOR_BUDGET_MS = 150000;
const AUTHOR_MAX_BUDGET_MS = 570000;
const COMMANDS = new Set([
  "system.ping",
  "douyin.author",
  "douyin.search",
  "google.search",
  "reddit.search",
  "tiktok.search",
  "twitter.search",
  "xiaohongshu.search",
]);

let offscreenInitialization;

function initializeOffscreenDocument() {
  if (offscreenInitialization) return offscreenInitialization;
  offscreenInitialization = (async () => {
    const contexts = await chrome.runtime.getContexts({
      contextTypes: ["OFFSCREEN_DOCUMENT"],
      documentUrls: [chrome.runtime.getURL(OFFSCREEN_DOCUMENT)],
    });
    if (contexts.length > 0) return;
    await chrome.offscreen.createDocument({
      url: OFFSCREEN_DOCUMENT,
      reasons: ["DOM_PARSER"],
      justification: "Maintain the authenticated localhost command channel.",
    });
  })().catch((error) => {
    offscreenInitialization = undefined;
    throw error;
  });
  return offscreenInitialization;
}

function errorEnvelope(id, kind, error) {
  return {
    id,
    ok: false,
    error: {
      kind,
      message: error instanceof Error ? error.message : String(error),
    },
  };
}

async function waitForTab(tabId, source, timeoutMs) {
  const current = await chrome.tabs.get(tabId);
  if (current.status === "complete") return;
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(onUpdated);
      reject(new Error(`${source} navigation timeout`));
    }, timeoutMs);
    function onUpdated(updatedTabId, changeInfo) {
      if (updatedTabId !== tabId || changeInfo.status !== "complete") return;
      clearTimeout(timeout);
      chrome.tabs.onUpdated.removeListener(onUpdated);
      resolve();
    }
    chrome.tabs.onUpdated.addListener(onUpdated);
  });
}

function requireQuery(payload) {
  const query = typeof payload.query === "string" ? payload.query.trim() : "";
  if (!query) throw new Error("query must be a non-empty string");
  return query;
}

function requireExtracted(source, extracted) {
  if (!extracted || typeof extracted.state !== "string") {
    const summary = extracted === undefined ? "undefined" : JSON.stringify(extracted);
    throw new Error(`${source} extractor returned an invalid state: ${summary}`);
  }
  if (extracted.state === "ready" || extracted.state === "empty") {
    return extracted.rows || extracted.cards || [];
  }
  if (extracted.state === "login") {
    throw new Error(
      extracted.message
        ? `${source} requires login in the connected Chrome profile (${extracted.message})`
        : `${source} requires login in the connected Chrome profile`,
    );
  }
  if (extracted.state === "blocked") {
    throw new Error(extracted.message || `${source} returned a verification wall`);
  }
  if (extracted.state === "timeout") {
    throw new Error(`${source} results did not render before timeout`);
  }
  if (extracted.state === "error") {
    throw new Error(extracted.message || `${source} extractor failed`);
  }
  throw new Error(`unknown ${source} extractor state: ${extracted.state}`);
}

async function injectExtractor(source, tabId, extractor, args, world) {
  const injected = await chrome.scripting.executeScript({
    target: { tabId },
    args,
    func: extractor,
    ...(world ? { world } : {}),
  });
  const injection = injected[0];
  if (injection && injection.error) {
    const message = injection.error.message || String(injection.error);
    throw new Error(`${source} extractor failed: ${message}`);
  }
  if (!injection || !("result" in injection)) {
    throw new Error(
      `${source} extractor returned no result envelope: ${JSON.stringify(injected)}`,
    );
  }
  return injection.result;
}

async function withTab(source, url, timeoutMs, run) {
  let tabId;
  try {
    const tab = await chrome.tabs.create({
      url,
      active: false,
    });
    tabId = tab.id;
    if (!tabId) {
      throw new Error(`Chrome did not create a ${source} tab`);
    }
    await waitForTab(tabId, source, timeoutMs);
    return await run(tabId);
  } finally {
    if (tabId) {
      await chrome.tabs.remove(tabId).catch(() => undefined);
    }
  }
}

async function withSearchTab(
  source,
  url,
  extractor,
  args,
  timeoutMs = 20000,
) {
  return withTab(source, url, timeoutMs, async (tabId) =>
    requireExtracted(source, await injectExtractor(source, tabId, extractor, args)),
  );
}

async function executeDouyinSearch(payload) {
  const query = requireQuery(payload);
  const limit = globalThis.OmnireachDouyin.normalizeLimit(payload.limit);
  const rows = await withSearchTab(
    "Douyin",
    `https://www.douyin.com/search/${encodeURIComponent(query)}?type=video`,
    async function extractDouyinCards(timeoutMs) {
      const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
      const deadline = Date.now() + timeoutMs;
      let previousCount = 0;
      let stableRounds = 0;
      while (Date.now() < deadline) {
        const pageText = document.body ? document.body.innerText : "";
        if (/登录后|扫码登录|验证码登录|密码登录/.test(pageText)) {
          return { state: "login", cards: [] };
        }
        const anchors = Array.from(
          document.querySelectorAll('[data-e2e="scroll-list"] a[href*="/video/"], a[href*="/video/"]'),
        );
        const unique = new Map();
        for (const anchor of anchors) {
          const href = anchor.getAttribute("href") || anchor.href || "";
          if (!/\/video\/\d+/.test(href) || unique.has(href)) continue;
          const leafTexts = (anchor.innerText || anchor.textContent || "")
            .split(/\n+/)
            .map((text) => text.trim())
            .filter(Boolean);
          unique.set(href, { href, leafTexts });
        }
        if (unique.size > 0) {
          stableRounds = unique.size === previousCount ? stableRounds + 1 : 0;
          previousCount = unique.size;
          if (stableRounds >= 2) return { state: "ready", cards: Array.from(unique.values()) };
          window.scrollBy(0, Math.max(window.innerHeight, 800));
        } else if (/暂无|没有找到|无相关/.test(pageText)) {
          return { state: "empty", cards: [] };
        }
        await delay(500);
      }
      return { state: "timeout", cards: [] };
    },
    [15000],
  );
  const projected = globalThis.OmnireachDouyin.projectCards(rows, limit);
  if (projected.invalidCount > 0 && projected.rows.length === 0) {
    throw new Error("Douyin result cards no longer match the expected shape");
  }
  return projected.rows;
}

async function extractDouyinUserCandidates(timeoutMs) {
  const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
  const deadline = Date.now() + timeoutMs;
  let previousCount = 0;
  let stableRounds = 0;
  let rows = [];
  while (Date.now() < deadline) {
    const pageText = document.body ? document.body.innerText : "";
    if (/登录后|扫码登录|验证码登录|密码登录/.test(pageText)) {
      return { state: "login", rows: [] };
    }
    const unique = new Map();
    for (const anchor of document.querySelectorAll('a[href*="/user/"]')) {
      const href = anchor.getAttribute("href") || anchor.href || "";
      const match = href.match(/\/user\/([A-Za-z0-9_-]+)/);
      if (!match || match[1] === "self" || unique.has(match[1])) continue;
      const lines = (anchor.innerText || anchor.textContent || "")
        .split(/\n+/)
        .map((text) => text.trim())
        .filter(Boolean);
      if (lines.length === 0) continue;
      unique.set(match[1], { secUid: match[1], lines });
    }
    rows = Array.from(unique.values());
    if (rows.length > 0) {
      stableRounds = rows.length === previousCount ? stableRounds + 1 : 0;
      previousCount = rows.length;
      if (stableRounds >= 2) return { state: "ready", rows };
    } else if (/没有找到|暂无|无相关/.test(pageText)) {
      return { state: "empty", rows: [] };
    }
    await delay(400);
  }
  return rows.length > 0 ? { state: "ready", rows } : { state: "timeout", rows: [] };
}

async function fetchDouyinAwemeBatch(
  secUid,
  startCursor,
  maxPages,
  includeMediaUrls,
  stopAfterUnpinned,
) {
  const trim = (item) => {
    const video = (item && item.video) || {};
    const stats = (item && item.statistics) || {};
    const author = (item && item.author) || {};
    const row = {
      aweme_id: item && item.aweme_id,
      desc: item && item.desc,
      create_time: item && item.create_time,
      duration: (item && item.duration) || video.duration,
      media_type: item && item.media_type,
      is_top: item && item.is_top,
      statistics: {
        digg_count: stats.digg_count,
        comment_count: stats.comment_count,
        share_count: stats.share_count,
        collect_count: stats.collect_count,
        play_count: stats.play_count,
      },
      author: { nickname: author.nickname, sec_uid: author.sec_uid },
      music: (item && item.music && item.music.title) || "",
      hashtags: ((item && item.text_extra) || [])
        .map((entry) => entry && entry.hashtag_name)
        .filter(Boolean),
      video_tags: ((item && item.video_tag) || [])
        .map((tag) => tag && tag.tag_name)
        .filter(Boolean),
    };
    if (includeMediaUrls) {
      const urls = (video.play_addr && video.play_addr.url_list) || [];
      if (urls[0]) row.play_url = urls[0];
    }
    return row;
  };

  const rows = [];
  let unpinned = 0;
  let cursor = String(startCursor);
  let pages = 0;
  while (pages < maxPages) {
    const params = new URLSearchParams({
      sec_user_id: secUid,
      max_cursor: cursor,
      count: "20",
      aid: "6383",
    });
    let response;
    try {
      response = await fetch(
        `https://www.douyin.com/aweme/v1/web/aweme/post/?${params}`,
        { credentials: "include", headers: { referer: "https://www.douyin.com/" } },
      );
    } catch (error) {
      return {
        state: "error",
        message: `Douyin catalog request failed: ${error && error.message}`,
        rows,
        cursor,
        hasMore: 1,
        pages,
      };
    }
    if (!response.ok) {
      // Say enough on the first failure to tell the three causes apart: a
      // rejected origin, a session that is not logged in, and a verification
      // challenge all arrive here looking alike otherwise.
      let snippet = "";
      try {
        snippet = (await response.text()).slice(0, 200).replace(/\s+/g, " ");
      } catch {
        snippet = "<unreadable body>";
      }
      const session = `cookie_chars=${document.cookie.length}`;
      const detail =
        `Douyin catalog API returned HTTP ${response.status} ` +
        `(${session}; body: ${snippet})`;
      const login = response.status === 401 || response.status === 403;
      return {
        state: login ? "login" : "blocked",
        message: detail,
        rows: login ? [] : rows,
        cursor,
        hasMore: 1,
        pages,
      };
    }
    let data;
    try {
      data = await response.json();
    } catch {
      return {
        state: "blocked",
        message:
          "Douyin catalog API returned a non-JSON body; a verification wall or a "
          + `signed-out session is likely (cookie_chars=${document.cookie.length})`,
        rows,
        cursor,
        hasMore: 1,
        pages,
      };
    }
    if (data && data.status_code) {
      return {
        state: "blocked",
        message: `Douyin catalog API answered status_code ${data.status_code}`,
        rows,
        cursor,
        hasMore: 1,
        pages,
      };
    }
    for (const item of Array.isArray(data.aweme_list) ? data.aweme_list : []) {
      const row = trim(item);
      if (!row.is_top) unpinned += 1;
      rows.push(row);
    }
    pages += 1;
    // Only has_more === 0 ends a catalog. Runs of empty pages in the middle are
    // normal — 19 consecutive empty pages measured on a 355-work account — so
    // stopping at the first empty page silently truncates the catalog.
    if (!data.has_more) {
      return { state: "ready", rows, cursor: String(data.max_cursor), hasMore: 0, pages };
    }
    const next = data.max_cursor;
    if (next === undefined || next === null || String(next) === cursor) {
      return { state: "ready", rows, cursor, hasMore: 0, pages, stalled: true };
    }
    cursor = String(next);
    // Pinned works are hoisted to the front and everything after them is
    // strictly newest-first, so once this many unpinned works are in hand every
    // work still unfetched is older than all of them.
    if (stopAfterUnpinned > 0 && unpinned >= stopAfterUnpinned) {
      return { state: "ready", rows, cursor, hasMore: 1, pages };
    }
  }
  return { state: "ready", rows, cursor, hasMore: 1, pages };
}

async function executeDouyinAuthor(payload) {
  const handle = typeof payload.handle === "string" ? payload.handle.trim() : "";
  if (!handle) throw new Error("handle must be a non-empty string");
  const limit = globalThis.OmnireachDouyin.normalizeAuthorLimit(payload.limit);
  const order = payload.order === "likes" ? "likes" : "recent";
  const includeMediaUrls = payload.include_media_urls === true;

  let secUid = globalThis.OmnireachDouyin.secUidFromInput(handle);
  let resolvedFrom = "url";
  let nickname = "";
  let followers = 0;
  if (!secUid) {
    const candidates = await withSearchTab(
      "Douyin user",
      `https://www.douyin.com/search/${encodeURIComponent(handle)}?type=user`,
      extractDouyinUserCandidates,
      [15000],
    );
    const picked = globalThis.OmnireachDouyin.pickUserCandidate(candidates, handle);
    if (!picked) {
      const seen = globalThis.OmnireachDouyin.userCandidates(candidates)
        .slice(0, 5)
        .map((row) => row.nickname)
        .join(", ");
      throw new Error(
        `Douyin user search for ${JSON.stringify(handle)} returned no account whose `
        + `name matches${seen ? `; it offered: ${seen}` : ""}. `
        + "Pass the profile URL to target an exact account.",
      );
    }
    secUid = picked.secUid;
    nickname = picked.nickname;
    followers = picked.followers;
    resolvedFrom = "search";
  }

  // Ranking by likes has to see every work; "recent" only needs enough unpinned
  // ones to be sure nothing newer is left unfetched.
  const stopAfter = order === "likes" ? 0 : limit;
  const requested = Number(payload.budget_ms);
  const budgetMs = Number.isFinite(requested) && requested > 0
    ? Math.min(Math.max(requested, 5000), AUTHOR_MAX_BUDGET_MS)
    : AUTHOR_BUDGET_MS;
  const deadline = Date.now() + budgetMs;
  const collected = [];
  const seen = new Set();
  let cursor = "0";
  let hasMore = 1;
  let pages = 0;
  let unpinned = 0;
  await withTab(
    "Douyin author",
    `https://www.douyin.com/user/${encodeURIComponent(secUid)}`,
    20000,
    async (tabId) => {
      while (hasMore && pages < AUTHOR_MAX_PAGES && Date.now() < deadline) {
        // MAIN world, not the default isolated world. A content-script fetch is
        // issued from the extension's own network context, and Douyin answers
        // it 403; measured 2026-09-03, dropping the Referer from a page-context
        // request changes nothing, so the rejected extension origin is what
        // matters. Inside the page this API needs no request signing at all.
        const batch = await injectExtractor(
          "Douyin author",
          tabId,
          fetchDouyinAwemeBatch,
          [secUid, cursor, AUTHOR_PAGES_PER_BATCH, includeMediaUrls, stopAfter],
          "MAIN",
        );
        requireExtracted("Douyin author", batch);
        for (const row of batch.rows || []) {
          const id = String(row && row.aweme_id);
          if (!id || seen.has(id)) continue;
          seen.add(id);
          if (!row.is_top) unpinned += 1;
          collected.push(row);
        }
        pages += batch.pages || 0;
        cursor = batch.cursor;
        hasMore = batch.hasMore;
        if (stopAfter > 0 && unpinned >= stopAfter) break;
      }
    },
  );

  const projected = globalThis.OmnireachDouyin.projectAwemeList(collected, limit, order);
  if (projected.invalidCount > 0 && projected.rows.length === 0) {
    throw new Error("Douyin catalog items no longer match the expected shape");
  }
  return [{
    sec_uid: secUid,
    nickname: nickname || (projected.rows[0] && projected.rows[0].author) || "",
    followers,
    resolved_from: resolvedFrom,
    order,
    pages,
    scanned: projected.scanned,
    returned: projected.rows.length,
    complete: !hasMore,
    works: projected.rows,
  }];
}

async function executeGoogleSearch(payload) {
  const query = requireQuery(payload);
  const limit = globalThis.OmnireachSites.normalizeLimit(payload.limit);
  const rows = await withSearchTab(
    "Google",
    `https://www.google.com/search?q=${encodeURIComponent(query)}&hl=en&num=${limit}`,
    async function extractGoogleRows(timeoutMs) {
      const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline && !document.querySelector("#rso a h3")) {
        const pageText = document.body ? document.body.innerText : "";
        if (/unusual traffic|not a robot|captcha/i.test(pageText)) {
          return { state: "blocked", message: "Google returned a CAPTCHA or unusual-traffic wall", rows: [] };
        }
        await delay(250);
      }
      const root = document.querySelector("#rso");
      if (!root) return { state: "timeout", rows: [] };
      const rows = [];
      const seen = new Set();
      for (const link of root.querySelectorAll("a")) {
        const heading = link.querySelector("h3");
        const href = link.href || "";
        if (!heading || !/^https?:/.test(href) || /google\.com\/search/.test(href) || seen.has(href)) continue;
        seen.add(href);
        let container = link;
        for (let depth = 0; depth < 6 && container.parentElement && container.parentElement !== root; depth += 1) {
          container = container.parentElement;
          if (container.hasAttribute && container.hasAttribute("data-hveid")) break;
        }
        let snippet = "";
        for (const candidate of container.querySelectorAll("span, div")) {
          if (candidate.querySelector("h3") || candidate.querySelector("a[href]")) continue;
          const text = (candidate.textContent || "").replace(/\s+/g, " ").trim();
          if (text.length >= 40 && text.length <= 500 && !text.includes("›") && !/^https?:/.test(text)) {
            snippet = text;
            break;
          }
        }
        rows.push({ type: "result", title: heading.textContent || "", url: href, snippet });
      }
      return { state: rows.length ? "ready" : "empty", rows };
    },
    [5000],
  );
  return globalThis.OmnireachSites.projectGoogle(rows, limit).rows;
}

async function executeRedditSearch(payload) {
  const query = requireQuery(payload);
  const limit = globalThis.OmnireachSites.normalizeLimit(payload.limit);
  const rows = await withSearchTab(
    "Reddit",
    "https://www.reddit.com/",
    async function extractRedditRows(searchQuery, count) {
      const decodeHtml = (value) => {
        const textarea = document.createElement("textarea");
        textarea.innerHTML = typeof value === "string" ? value : "";
        return textarea.value;
      };
      const response = await fetch(
        `/search.json?q=${encodeURIComponent(searchQuery)}&sort=relevance&t=all&limit=${count}&raw_json=1`,
        { credentials: "include" },
      );
      const contentType = response.headers.get("content-type") || "";
      if (!response.ok || !contentType.includes("json")) {
        return {
          state: "blocked",
          message: `Reddit search returned HTTP ${response.status} instead of JSON; login or verification may be required`,
          rows: [],
        };
      }
      const data = await response.json();
      const children = data && data.data && Array.isArray(data.data.children) ? data.data.children : [];
      const rows = children.map((child) => {
        const post = child.data || {};
        const galleryUrls = [];
        for (const item of (post.gallery_data && post.gallery_data.items) || []) {
          const media = post.media_metadata && post.media_metadata[item.media_id];
          if (media && media.s && media.s.u) galleryUrls.push(decodeHtml(media.s.u));
        }
        return {
          id: post.id,
          title: post.title,
          subreddit: post.subreddit_name_prefixed,
          author: post.author,
          score: post.score,
          comments: post.num_comments,
          url: post.permalink ? `https://www.reddit.com${post.permalink}` : "",
          created_utc: post.created_utc,
          selftext: post.selftext || "",
          post_hint: post.post_hint || "",
          url_overridden_by_dest: post.url_overridden_by_dest || "",
          preview_image_url: decodeHtml(
            post.preview &&
            post.preview.images &&
            post.preview.images[0] &&
            post.preview.images[0].source &&
            post.preview.images[0].source.url,
          ),
          gallery_urls: galleryUrls,
        };
      });
      return { state: rows.length ? "ready" : "empty", rows };
    },
    [query, limit],
  );
  return globalThis.OmnireachSites.projectReddit(rows, limit).rows;
}

async function executeTikTokSearch(payload) {
  const query = requireQuery(payload);
  const limit = globalThis.OmnireachSites.normalizeLimit(payload.limit);
  const rows = await withSearchTab(
    "TikTok",
    `https://www.tiktok.com/search?q=${encodeURIComponent(query)}`,
    async function extractTikTokRows(count, timeoutMs) {
      const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
      const deadline = Date.now() + timeoutMs;
      const cards = () => Array.from(document.querySelectorAll('[data-e2e="search_top-item"]'));
      let previousCount = 0;
      let stableRounds = 0;
      while (Date.now() < deadline) {
        const pageText = document.body ? document.body.innerText : "";
        if (/verify to continue|security verification|captcha/i.test(pageText)) {
          return {
            state: "blocked",
            message: "TikTok returned a verification wall",
            rows: [],
          };
        }
        const current = cards();
        if (current.length >= count || (current.length > 0 && stableRounds >= 2)) break;
        stableRounds = current.length === previousCount ? stableRounds + 1 : 0;
        previousCount = current.length;
        window.scrollBy(0, Math.max(window.innerHeight, 800));
        await delay(500);
      }
      const rows = [];
      const seen = new Set();
      for (const item of cards()) {
        const card = item.parentElement || item;
        const videoLink = item.querySelector('a[href*="/video/"]')
          || card.querySelector('a[href*="/video/"]');
        const url = (videoLink && videoLink.href) || "";
        if (!/\/video\/\d+/.test(url) || seen.has(url)) continue;
        seen.add(url);
        const caption = card.querySelector('[data-e2e="search-card-video-caption"]');
        const author = card.querySelector('[data-e2e="search-card-user-unique-id"]');
        const views = item.querySelector('[data-e2e="video-views"]')
          || card.querySelector('[data-e2e="video-views"]');
        rows.push({
          desc: (caption && caption.textContent) || "",
          author: (author && author.textContent) || "",
          url,
          plays: (views && views.textContent) || "0",
          likes: 0,
          comments: 0,
          shares: 0,
        });
        if (rows.length >= count) break;
      }
      if (rows.length) return { state: "ready", rows };
      const pageText = document.body ? document.body.innerText : "";
      if (/no results found|couldn't find/i.test(pageText)) return { state: "empty", rows: [] };
      return { state: "timeout", rows: [] };
    },
    [limit, 15000],
  );
  return globalThis.OmnireachSites.projectTikTok(rows, limit).rows;
}

async function executeXiaohongshuSearch(payload) {
  const query = requireQuery(payload);
  const limit = globalThis.OmnireachSites.normalizeLimit(payload.limit);
  const rows = await withSearchTab(
    "Xiaohongshu",
    `https://www.xiaohongshu.com/search_result?keyword=${encodeURIComponent(query)}&source=web_search_result_notes`,
    async function extractXiaohongshuRows(count, timeoutMs) {
      const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
      const deadline = Date.now() + timeoutMs;
      const cards = () => {
        const direct = Array.from(document.querySelectorAll("section.note-item"));
        if (direct.length) return direct;
        return Array.from(new Set(Array.from(document.querySelectorAll('a[href*="/search_result/"], a[href*="/explore/"]')).map((link) => link.closest("section")).filter(Boolean)));
      };
      let previousCount = 0;
      let stableRounds = 0;
      while (Date.now() < deadline) {
        const pageText = document.body ? document.body.innerText : "";
        if (/登录后查看搜索结果|扫码登录|验证码登录/.test(pageText)) return { state: "login", rows: [] };
        const current = cards();
        if (current.length >= count || (current.length > 0 && stableRounds >= 2)) break;
        stableRounds = current.length === previousCount ? stableRounds + 1 : 0;
        previousCount = current.length;
        window.scrollTo(0, document.body.scrollHeight);
        await delay(700);
      }
      const rows = [];
      const seen = new Set();
      for (const card of cards()) {
        if (card.classList && card.classList.contains("query-note-item")) continue;
        const detail = card.querySelector('a.cover.mask, a[href*="/search_result/"], a[href*="/explore/"], a[href*="/note/"]');
        const rawHref = detail && detail.getAttribute("href");
        const url = rawHref && rawHref.startsWith("/") ? `https://www.xiaohongshu.com${rawHref}` : rawHref || "";
        if (!url || seen.has(url)) continue;
        seen.add(url);
        const titleElement = card.querySelector(".title, .note-title, a.title, .footer .title span") || (detail && detail.querySelector("span"));
        const authorLink = card.querySelector('a.author, a[href*="/user/profile/"]');
        const authorElement = card.querySelector("a.author .name, .author-name, .nick-name, .name");
        const likesElement = card.querySelector(".count, .like-count, .like-wrapper .count");
        rows.push({
          title: (titleElement && titleElement.textContent) || "",
          author: (authorElement && authorElement.textContent) || (authorLink && authorLink.textContent) || "",
          author_url: (authorLink && authorLink.href) || "",
          likes: (likesElement && likesElement.textContent) || "0",
          url,
        });
        if (rows.length >= count) break;
      }
      if (rows.length) return { state: "ready", rows };
      return { state: Date.now() >= deadline ? "timeout" : "empty", rows: [] };
    },
    [limit, 15000],
  );
  return globalThis.OmnireachSites.projectXiaohongshu(rows, limit).rows;
}

async function executeTwitterSearch(payload) {
  const query = requireQuery(payload);
  const limit = globalThis.OmnireachSites.normalizeLimit(payload.limit);
  const rows = await withSearchTab(
    "Twitter",
    `https://x.com/search?q=${encodeURIComponent(query)}&src=typed_query&f=top`,
    async function extractTwitterRows(count, timeoutMs) {
      const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
      const deadline = Date.now() + timeoutMs;
      let previousCount = 0;
      let stableRounds = 0;
      while (Date.now() < deadline) {
        const pageText = document.body ? document.body.innerText : "";
        if (/Sign in to X|Log in to X|登录 X|登录后/.test(pageText) && !document.querySelector('article[data-testid="tweet"]')) {
          return { state: "login", rows: [] };
        }
        const countNow = document.querySelectorAll('article[data-testid="tweet"]').length;
        if (countNow >= count || (countNow > 0 && stableRounds >= 2)) break;
        stableRounds = countNow === previousCount ? stableRounds + 1 : 0;
        previousCount = countNow;
        window.scrollBy(0, Math.max(window.innerHeight, 800));
        await delay(500);
      }
      const rows = [];
      const seen = new Set();
      const displayCount = (element) => {
        if (!element) return "0";
        const label = element.getAttribute("aria-label") || "";
        const match = label.match(/[\d,.]+\s*[KMB]?/i);
        return (element.innerText || (match && match[0]) || "0").trim();
      };
      for (const article of document.querySelectorAll('article[data-testid="tweet"]')) {
        const statusLink = Array.from(article.querySelectorAll('a[href*="/status/"]')).find((link) => link.querySelector("time"));
        const href = statusLink && statusLink.href;
        if (!href || seen.has(href)) continue;
        seen.add(href);
        const textElement = article.querySelector('[data-testid="tweetText"]');
        const userBlock = article.querySelector('[data-testid="User-Name"]');
        const handleLink = userBlock && Array.from(userBlock.querySelectorAll("a[href]"))
          .find((link) => /^\/[^/]+$/.test(new URL(link.href).pathname));
        const statusAuthor = new URL(href).pathname.match(/^\/([^/]+)\/status\/\d+/);
        const media = Array.from(article.querySelectorAll('img[src*="pbs.twimg.com/media"], video'));
        const analytics = article.querySelector('a[href*="/analytics"]');
        rows.push({
          text: (textElement && textElement.textContent) || "",
          author: handleLink
            ? new URL(handleLink.href).pathname.slice(1)
            : (statusAuthor && statusAuthor[1]) || "",
          created_at: (statusLink.querySelector("time") && statusLink.querySelector("time").getAttribute("datetime")) || "",
          replies: displayCount(article.querySelector('[data-testid="reply"]')),
          retweets: displayCount(article.querySelector('[data-testid="retweet"]')),
          likes: displayCount(article.querySelector('[data-testid="like"]')),
          views: displayCount(analytics),
          url: href,
          has_media: media.length > 0,
          media_urls: media.map((element) => element.currentSrc || element.src || "").filter(Boolean),
        });
        if (rows.length >= count) break;
      }
      if (rows.length) return { state: "ready", rows };
      const pageText = document.body ? document.body.innerText : "";
      if (/No results for|Try searching for something else/i.test(pageText)) return { state: "empty", rows: [] };
      return { state: "timeout", rows: [] };
    },
    [limit, 15000],
  );
  return globalThis.OmnireachSites.projectTwitter(rows, limit).rows;
}

const SEARCH_HANDLERS = Object.freeze({
  "douyin.author": executeDouyinAuthor,
  "douyin.search": executeDouyinSearch,
  "google.search": executeGoogleSearch,
  "reddit.search": executeRedditSearch,
  "tiktok.search": executeTikTokSearch,
  "twitter.search": executeTwitterSearch,
  "xiaohongshu.search": executeXiaohongshuSearch,
});

async function executeJob(job) {
  if (!job || typeof job.id !== "string" || !COMMANDS.has(job.command)) {
    const received = job && job.command;
    return errorEnvelope(
      job && job.id,
      "contract",
      `command is not allowed: ${JSON.stringify(received)}; allowed=${JSON.stringify(Array.from(COMMANDS).sort())}`,
    );
  }
  try {
    if (job.command === "system.ping") {
      return {
        id: job.id,
        ok: true,
        items: [{
          pong: true,
          extensionVersion: EXTENSION_VERSION,
          commands: Array.from(COMMANDS).sort(),
        }],
      };
    }
    const items = await SEARCH_HANDLERS[job.command](job.payload || {});
    return { id: job.id, ok: true, items };
  } catch (error) {
    return errorEnvelope(job.id, "runtime", error);
  }
}

chrome.runtime.onMessage.addListener((message) => {
  if (!message || message.type !== "run-job") return undefined;
  return executeJob(message.job);
});

chrome.runtime.onInstalled.addListener(() => void initializeOffscreenDocument());
chrome.runtime.onStartup.addListener(() => void initializeOffscreenDocument());
void initializeOffscreenDocument();
