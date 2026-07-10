importScripts("douyin.js");

const OFFSCREEN_DOCUMENT = "offscreen.html";
const COMMANDS = new Set(["system.ping", "douyin.search"]);

async function ensureOffscreenDocument() {
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

async function waitForTab(tabId, timeoutMs) {
  const current = await chrome.tabs.get(tabId);
  if (current.status === "complete") return;
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(onUpdated);
      reject(new Error("Douyin navigation timeout"));
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

async function executeDouyinSearch(payload) {
  const query = typeof payload.query === "string" ? payload.query.trim() : "";
  if (!query) throw new Error("query must be a non-empty string");
  const limit = globalThis.OmnireachDouyin.normalizeLimit(payload.limit);
  const url = `https://www.douyin.com/search/${encodeURIComponent(query)}?type=video`;
  let windowId;
  try {
    const created = await chrome.windows.create({
      url,
      focused: false,
      state: "minimized",
      type: "normal",
    });
    windowId = created.id;
    const tab = created.tabs && created.tabs[0];
    if (!windowId || !tab || !tab.id) {
      throw new Error("Chrome did not create a Douyin search tab");
    }
    await waitForTab(tab.id, 15000);
    const injected = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      args: [15000],
      func: async function extractDouyinCards(timeoutMs) {
        const delay = (milliseconds) =>
          new Promise((resolve) => setTimeout(resolve, milliseconds));
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
            const card =
              anchor.closest("li, article, [data-e2e], [class*='card']") ||
              anchor.parentElement;
            const leafTexts = Array.from(
              (card || anchor).querySelectorAll("span, p, h1, h2, h3, a"),
            )
              .filter((node) => node.children.length === 0)
              .map((node) => (node.textContent || "").trim())
              .filter(Boolean);
            unique.set(href, { href, leafTexts });
          }
          if (unique.size > 0) {
            stableRounds = unique.size === previousCount ? stableRounds + 1 : 0;
            previousCount = unique.size;
            if (stableRounds >= 2) {
              return { state: "ready", cards: Array.from(unique.values()) };
            }
            window.scrollBy(0, Math.max(window.innerHeight, 800));
          } else if (/暂无|没有找到|无相关/.test(pageText)) {
            return { state: "empty", cards: [] };
          }
          await delay(500);
        }
        return { state: "timeout", cards: [] };
      },
    });
    const extracted = injected[0] && injected[0].result;
    if (!extracted || typeof extracted.state !== "string") {
      throw new Error("Douyin extractor returned an invalid state");
    }
    if (extracted.state === "login") {
      throw new Error("Douyin requires login in the connected Chrome profile");
    }
    if (extracted.state === "timeout") {
      throw new Error("Douyin results did not render before timeout");
    }
    if (extracted.state === "empty") return [];
    if (extracted.state !== "ready") {
      throw new Error(`unknown Douyin extractor state: ${extracted.state}`);
    }
    const projected = globalThis.OmnireachDouyin.projectCards(
      extracted.cards,
      limit,
    );
    if (projected.invalidCount > 0 && projected.rows.length === 0) {
      throw new Error("Douyin result cards no longer match the expected shape");
    }
    return projected.rows;
  } finally {
    if (windowId) {
      await chrome.windows.remove(windowId).catch(() => undefined);
    }
  }
}

async function executeJob(job) {
  if (!job || typeof job.id !== "string" || !COMMANDS.has(job.command)) {
    return errorEnvelope(job && job.id, "contract", "command is not allowed");
  }
  try {
    if (job.command === "system.ping") {
      return { id: job.id, ok: true, items: [{ pong: true, version: "0.1.0" }] };
    }
    const items = await executeDouyinSearch(job.payload || {});
    return { id: job.id, ok: true, items };
  } catch (error) {
    return errorEnvelope(job.id, "runtime", error);
  }
}

chrome.runtime.onMessage.addListener((message) => {
  if (!message || message.type !== "run-job") return undefined;
  return executeJob(message.job);
});

chrome.runtime.onInstalled.addListener(() => void ensureOffscreenDocument());
chrome.runtime.onStartup.addListener(() => void ensureOffscreenDocument());
void ensureOffscreenDocument();
