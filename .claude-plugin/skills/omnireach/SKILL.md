---
name: omnireach
description: Give your agent the senses of a logged-in human across the whole internet — search AND read 15+ platforms (Twitter / Reddit / 小红书 / 微信公众号 / 抖音 / B站 / TikTok / YouTube / HackerNews / GitHub / RSS) including the login-walled vertical sources that no web search reaches, via the user's own browser session. Two commands: `omnireach search <query>` (metadata + URL) and `omnireach fetch <url>` (full markdown). Use when the user wants to search or read any of these platforms, shares a URL to read, asks to research a topic, OR when Claude Code's built-in WebSearch is unavailable (proxy / relay-station / Bedrock / Vertex-Claude3.x environments where the web_search_20250305 server tool isn't implemented).
---

# omnireach — 全网通搜索 + 全文抓取

omnireach 是一个 CLI 工具集, 把 web 搜索 + 多平台读取 (Twitter / Reddit / YouTube / B站 / 小红书 / HN / GitHub / 微信公众号 / RSS) 整合到一条命令里。Claude Code 的 WebSearch 是 server tool, 真实可用性经过两层 gate: (a) 客户端 `isEnabled()` 看 `CLAUDE_CODE_USE_*` env var (默认 firstParty 注册 tool, 显式 Bedrock 关); (b) 上游 API 必须**专门实现** `web_search_20250305` server tool (Anthropic / DeepSeek / Foundry / Vertex+Claude4+ 等专门做 Claude Code 兼容的都实现; 单纯做 API 转译的 OpenAI 兼容中转站和大部分自托管 gateway 不实现)。omnireach 给两层 gate 任一关掉的用户补一个客户端实现的多源 search + fetch。同时即使 WebSearch 可用, 它也搜不到 Twitter / 小红书 / 微信公众号 等纵向源, omnireach 也能补齐。

v0.10 起两个核心子命令:
- `omnireach search <query>` → 全网 SERP (metadata + URL)
- `omnireach fetch <url>` → URL 拉成全文 markdown — host-aware: `mp.weixin.qq.com` 走 OpenCLI 登录态 Chrome (v0.10.1+, 绕过验证码), 其它 host 走 crwl 优先 + Jina Reader fallback

## Agent 调用约定 (重要)

**作为 Agent 调用 omnireach 时, 永远显式拿 JSON**。两种方式任选 (或都用, belt + suspenders):

1. **每条命令加 `--json`**: `omnireach search --json "..."` / `omnireach fetch --json "<url>"`
2. **设环境变量** (一次性, 整个 Agent harness 生效): `export OMNIREACH_FORCE_JSON=1`

为什么需要: omnireach 默认在 TTY 下出 rich.Table (人类友好), 但 Agent 拿到 wrap 过的 table 文本抠 URL/字段是噩梦。v0.9.2 加了 `not isatty()` 自动 JSON, 但某些 Agent 终端 (如 Antigravity) 会给子进程分配真 PTY 让 `isatty()=True`, 自动检测就失效 —— 显式 `--json` 或 env var 是 always-works 保险。

## 如何使用

### 第一次用 / step 0 (自愈)

如果 `omnireach` 不在 PATH (skill 在但 CLI 没装), 先跑这一条幂等命令装好 CLI + skill, 然后正常用:

```bash
curl -fsSL https://raw.githubusercontent.com/Daily-AC/omnireach/main/install.sh | sh
```

零配置即可用: hackernews / rss / wechat (Sogou 免费) / bilibili (B站官方 API)。其他源 (twitter / reddit / xhs / tiktok / douyin / boosters) 跑 `omnireach setup <source>` 解锁 (注意: `setup` 是交互式, 给人用; agent 别直接调)。

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

### Fetch — URL → 全文 markdown (v0.10, v0.10.1 加 OpenCLI 路径)

```bash
omnireach fetch --json "https://mp.weixin.qq.com/s/abc"        # auto → opencli (登录态)
omnireach fetch --json "https://example.com/article"           # auto → crwl → jina
```

返回:
```json
{
  "url": "...",
  "backend": "opencli" | "crwl" | "jina" | null,
  "fetched_at": "ISO 8601 Z",
  "content_markdown": "# title\n\nbody...",
  "errors": [{"code": "captcha_suspected" | "opencli_failed" | "backend_unavailable" | ...,
              "detail": "..."}]
}
```

Backend 选择:
- `--backend auto` (default): **host-aware** — `mp.weixin.qq.com` URL 强走 opencli (登录态 cookie-strategy, 绕过验证码); 其它 host 走 crwl (本地 Crawl4AI, 反爬强) 优先 + jina (Jina Reader SaaS, `r.jina.ai/<url>`, 免费额度大, 零配置) fallback
- `--backend opencli`: 强制走 OpenCLI weixin 登录态路径 (只对 `mp.weixin.qq.com` 有意义, 其它 host 报 `backend_unavailable`)
- `--backend crwl`: 强制走 Crawl4AI 本地, 没装就报错 (装: `pip install -U crawl4ai && crawl4ai-setup`)
- `--backend jina`: 强制走 Jina Reader, 零依赖

**CAPTCHA 启发式兜底** (v0.10.1+): 所有 backend 拿到响应后扫验证页关键词 (环境异常 / 完成验证后即可继续访问 / Cloudflare / Just a moment 等), 命中 → `errors[]` 加 `captcha_suspected` entry, **`content_markdown` 字段保留**, Agent 自己读 errors 决定信不信。

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
# 返 {
#   sources: [...],
#   fetch_backends: [{tool: "crwl", ok: true|false, ...}],
#   wechat_backends: [{tool: "opencli weixin", ok: true|false, ...}]   # v0.10.1+
# }
```

`wechat_backends` 段检测 OpenCLI 是否在 PATH + `weixin download` 是否支持 `--stdout` flag (依赖 Daily-AC/OpenCLI fork commit fe28823+, 上游 PR jackwener/OpenCLI#1770 等 review)。没装/老版本 → 给出 `npm i -g github:Daily-AC/OpenCLI` 升级提示。

## 何时用 omnireach 而不是其他工具

- **用 `omnireach search`**: 用户在中转站环境, 或想搜 Twitter/Reddit/小红书/B站 等原生 WebSearch 不擅长的源
- **用 `omnireach fetch`**: 拿到 URL 后想取全文 markdown。`mp.weixin.qq.com` 这类反爬强 + 需要登录态的站点会自动走 OpenCLI 通道, 普通网页走 crwl/jina
- **不用**: 简单的网页打开 (用 WebFetch), 或代码搜索 (用 grep/Grep)
