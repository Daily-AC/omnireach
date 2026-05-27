---
name: omnireach
description: Use when the user needs to search the web or read content from Twitter / Reddit / YouTube / Bilibili / 小红书 / TikTok / 抖音 / HackerNews / GitHub / 微信公众号 / RSS, especially when the built-in WebSearch is unavailable (proxy/relay stations). Provides a unified search command + a unified fetch command (URL → full markdown) across multiple platforms.
---

# omnireach — 全网通搜索 + 全文抓取

omnireach 是一个 CLI 工具集, 把 web 搜索 + 多平台读取 (Twitter / Reddit / YouTube / B站 / 小红书 / HN / GitHub / 微信公众号 / RSS) 整合到一条命令里. 对于用中转站、装不上 Anthropic 原生 WebSearch 的同学, 这是一个"全网通"替代品.

v0.10 起两个核心子命令:
- `omnireach search <query>` → 全网 SERP (metadata + URL)
- `omnireach fetch <url>` → URL 拉成全文 markdown (crwl 优先, Jina Reader fallback)

## Agent 调用约定 (重要)

**作为 Agent 调用 omnireach 时, 永远显式拿 JSON**。两种方式任选 (或都用, belt + suspenders):

1. **每条命令加 `--json`**: `omnireach search --json "..."` / `omnireach fetch --json "<url>"`
2. **设环境变量** (一次性, 整个 Agent harness 生效): `export OMNIREACH_FORCE_JSON=1`

为什么需要: omnireach 默认在 TTY 下出 rich.Table (人类友好), 但 Agent 拿到 wrap 过的 table 文本抠 URL/字段是噩梦。v0.9.2 加了 `not isatty()` 自动 JSON, 但某些 Agent 终端 (如 Antigravity) 会给子进程分配真 PTY 让 `isatty()=True`, 自动检测就失效 —— 显式 `--json` 或 env var 是 always-works 保险。

## 如何使用

### 第一次用 (用户没装过)

```bash
pipx install omnireach && omnireach init
```

零配置可用: hackernews / rss / wechat (Sogou 免费) / bilibili (B站官方 API)。其他源 (twitter / reddit / xhs / tiktok / douyin / boosters) 跑 `omnireach setup <source>` 解锁。

### Search — 拿 URL + metadata

```bash
omnireach search --json "Claude 4.7 prompt caching 实测"
```

返回标准化 envelope:
```json
{
  "query": "...",
  "ts": "ISO 8601 Z",
  "results": [{"source", "adapter", "title", "url", "content", "ts", "score", "engagement", "raw", "cost"}],
  "errors": [{"source", "error", "category": "unavailable" | "failed"}]
}
```

注意: `content` 字段是 SERP snippet (≤ 500 字 + "…", v0.8 起 contract 层强制截断)。要全文用 `omnireach fetch <url>`。

### Fetch — URL → 全文 markdown (v0.10)

```bash
omnireach fetch --json "https://mp.weixin.qq.com/s/abc"
```

返回:
```json
{
  "url": "...",
  "backend": "crwl" | "jina" | null,
  "fetched_at": "ISO 8601 Z",
  "content_markdown": "# title\n\nbody...",
  "errors": ["crwl: ...", "jina: ..."]
}
```

Backend 选择:
- `--backend auto` (default): crwl (本地 Crawl4AI, 反爬强) 优先, 失败/没装 fallback 到 jina (Jina Reader SaaS, `r.jina.ai/<url>`, 免费额度大, 零配置)
- `--backend crwl`: 只用 crwl, 没装就报错 (装: `pip install -U crawl4ai && crawl4ai-setup`)
- `--backend jina`: 只用 jina, 零依赖

### Search + Fetch 组合 pipeline

```bash
# 拿 wechat 公众号搜索结果的全文
omnireach search --on wechat --json "claude 4.7" \
  | jq -r '.results[].url' \
  | xargs -I{} omnireach fetch --json {}
```

### 限定源

```bash
omnireach search --on twitter,reddit --json "anyrouter 跑路"
omnireach search --on hackernews --json "show hn omnireach"
```

### 模式

```bash
omnireach search --mode quick "...."  # 只查 hackernews
omnireach search --mode deep  "...."  # 全部就绪源
```

### Doctor — 检查源 + fetch backend 状态

```bash
omnireach doctor --json
# 返 {sources: [...], fetch_backends: [{tool: "crwl", ok: true|false, ...}]}
```

## 何时用 omnireach 而不是其他工具

- **用 `omnireach search`**: 用户在中转站环境, 或想搜 Twitter/Reddit/小红书/B站 等原生 WebSearch 不擅长的源
- **用 `omnireach fetch`**: 拿到 URL 后想取全文 markdown, 尤其是反爬较强的 mp.weixin.qq.com 这类站点
- **不用**: 简单的网页打开 (用 WebFetch), 或代码搜索 (用 grep/Grep)
