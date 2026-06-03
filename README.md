# omnireach

> 全网通搜索 — 一个 CLI + Claude Code Skill, 给中转站 Agent 用户补齐 WebSearch + 多平台读取能力.

> **Works with**: Claude Code · Antigravity (`agy`) · 任何识别 `.claude-plugin/` manifest 的 Agent CLI。
> v0.5.1 实测过 `agy plugin install` 走通完整 SKILL 路由流程。

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)

## 关于命名: omnireach 是项目名, 同 repo 会出多个 sibling binary

**omnireach** = `omni` (全部) + `reach` (触达)。完整的"触达全网"语义其实需要三层能力, 三层都会作为**本 repo 内的 sibling binary** 存在 (类比 `cargo` / `rustc` / `rustfmt` 同 Rust repo 模式, **不开 sister repo**):

| 层 | 实现 | 职责 | 状态 |
|---|---|---|---|
| **search** | `omnireach search` subcommand | 全网定位 — 返 metadata + URL, 不取内容 | ✅ v0.7+ 在用 |
| **fetch** | `omnireach fetch` subcommand | 给定 URL 取全文 markdown — host-aware: `mp.weixin.qq.com` 走 OpenCLI 登录态, 其它走 [Crawl4AI](https://github.com/unclecode/crawl4ai) → [Jina Reader](https://r.jina.ai/) | ✅ v0.10+ (wechat 路径 v0.10.1+) |
| **parse** | (暂未实现, 未来加在本 repo) | 视频/音频内容解析 (字幕/STT/逐帧) | 🔜 未启动 |

v0.10 起 `omnireach` 同时负责 search + fetch 两层 (subcommand 形式), 不再是单一 search 工具。想解析视频暂时仍走 yt-dlp / whisper 这类外部工具组合, parse binary 等真有用户需求才在本 repo 加 (YAGNI)。

这样拆是有意为之 (对照 Anthropic Claude 自己的 [WebSearch](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-search) + [WebFetch](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-fetch) 拆分): 每层 do one thing well, 不让 search 被解析任务拖累 token 和延迟, 也让 Agent 调用方有自由组合的空间。

> ℹ️  曾考虑把 `omnireach` binary 改名 `omnisearch`, 但 v0.10 落地 `omnireach fetch` subcommand 后该问题消解 —— `omnireach search` (触达 = 找) + `omnireach fetch` (触达 = 取) 都是 reach 的合理子动作, umbrella 名留给项目愿景。**不改名** (2026-05-27 decided).

## 为什么需要 omnireach

Claude Code 的 WebSearch 是**服务端 server tool** (`web_search_20250305`), 真实可用性其实经过 **两层 gate**:

**1. 客户端 gate** — `WebSearchTool.isEnabled()` 看 `getAPIProvider()`:
- 默认 `firstParty` (没设 `CLAUDE_CODE_USE_*` env var 时, 包括只改了 `ANTHROPIC_BASE_URL` 的场景) → tool **注册**
- 显式 `CLAUDE_CODE_USE_BEDROCK=1` → tool 关
- 显式 `CLAUDE_CODE_USE_VERTEX=1` + Claude 4+ → 注册, 老 Claude → 关
- 显式 `CLAUDE_CODE_USE_FOUNDRY=1` → 注册

**2. 上游服务 gate** — 客户端把 tool schema 发出去后, 上游 API 必须真懂 `web_search_20250305` 这个 Anthropic-native server tool:
- 真 Anthropic API (api.anthropic.com): ✓ 服务端跑 WebSearch
- Vertex / Foundry: ✓ (model 在支持列表里时)
- **OpenAI 兼容中转站** (cliproxy / anyrouter 等): 客户端把它当 firstParty 发 tool, **但上游底层是 OpenAI / Gemini / Claude API wrapper**, 不识 server tool → 失败
- **自托管 gateway / 任何改 `ANTHROPIC_BASE_URL` 的 proxy**: 取决于 gateway 是否真转发到 Anthropic + 是否保留 server tool 语义 (大多数不保留)

也就是说, 几个常见痛点的**真根因不一样**:
- 中转站用户: 客户端发了 tool, **上游不是真 Anthropic** 处理不了
- 显式 Bedrock 用户 / Vertex Claude 3.x 用户: 客户端就关了
- 自托管 gateway: 看 gateway 实现 (一般不实现)

而且即使你**真有** WebSearch (firstParty 直连或 Vertex 4+), 它也搜不全 — Twitter 实时讨论 / Reddit 深度评论 / 小红书种草 / 微信公众号文章 / 抖音 / B站技术视频 这些纵向源, 服务端 WebSearch 几乎都够不着。

omnireach 给所有这些用户补一个**客户端实现的多源 search + fetch CLI** (绕过两层 gate, 直接走 OpenCLI Chrome 桥 / `yt-dlp` / `gh` / 各付费 search API), 对外只暴露一个轻量 CLI + 一个 Claude Skill, **3 分钟内**装好就能用。

## 快速开始

```bash
uv tool install git+https://github.com/Daily-AC/omnireach.git
omnireach init                  # 写默认 ~/.omnireach/preferences.toml
omnireach search "vibe coding"  # HN 立即可用 (零配置)
```

零配置只跑 HackerNews。要打开其他源:

```bash
omnireach setup youtube   # pip install yt-dlp
omnireach setup github    # 提示 brew install gh (macOS)
omnireach setup reddit    # uv tool install rdt-cli + rdt login
omnireach setup exa       # 拿 EXA_API_KEY (付费 web search)
```

### 在 Claude Code 里用

```
/plugin marketplace add Daily-AC/omnireach
/plugin install omnireach
```

然后在对话里直接说: "用 omnireach 搜一下 ..."

## 命令

| 命令 | 干嘛 |
|---|---|
| `omnireach search "<query>"` | 搜索 (SERP: metadata + URL) |
| `omnireach search --on twitter,reddit "..."` | 指定源 |
| `omnireach search --mode quick "..."` | 只查 hn |
| `omnireach search --mode deep "..."` | 查所有就绪源 |
| `omnireach search --json "..."` | 显式 JSON 输出 |
| **`omnireach fetch <url>`** (v0.10, v0.10.1) | **URL → 全文 markdown** — `mp.weixin.qq.com` 走 OpenCLI 登录态 Chrome (v0.10.1+), 其它 host 走 crwl → jina fallback |
| `omnireach fetch <url> --backend jina` | 强制走 Jina Reader SaaS (零本地依赖) |
| `omnireach fetch <url> --backend opencli` | 强制走 OpenCLI weixin 登录态路径 (v0.10.1+) |
| `omnireach init` | 写默认 `~/.omnireach/preferences.toml` |
| `omnireach sources` | 列出所有源 + 心愿单状态 |
| `omnireach setup <source>` | 引导式配置一个 🟡 / 🔴 源 |
| `omnireach doctor` | 健康检查 (含 sources / fetch backends / wechat backends) |

### Agent 调用约定 (v0.10)

作为 Agent 调用 omnireach 时, **永远显式拿 JSON**, 防止 TTY 表格 wrap 让你抠不到字段:

```bash
# 方式 1: 每条命令加 --json
omnireach search --json "..."
omnireach fetch  --json "<url>"

# 方式 2: 一次性 env (整个 Agent harness 生效, 推荐)
export OMNIREACH_FORCE_JSON=1
```

v0.9.2 加的 `not isatty()` 自动 JSON 在大多数场景够用, 但有些 Agent 终端 (如 Antigravity) 给子进程分配真 PTY 让 isatty()=True, 自动检测失效 —— 显式 `--json` 或 env var 是 always-works 保险。

## 支持的源

| 源 | tier | 依赖 | 说明 |
|---|---|---|---|
| hackernews | ✅ ready | 无 | 直连 Algolia, 零配置 |
| youtube | ✅ ready | `yt-dlp` (pip install) | `omnireach setup youtube` |
| github | ✅ ready | `gh` CLI + `gh auth login` | `omnireach setup github` |
| rss | ✅ ready | 内置 feedparser | query 必须是 URL |
| reddit | 🟡 one_step | `rdt-cli` + `rdt login` | `omnireach setup reddit` |
| twitter | 🔴 heavy | OpenCLI + Chrome 扩展 | v0.3 路径 |
| xiaohongshu | 🔴 heavy | OpenCLI + Chrome 扩展 | v0.3 路径 |
| tiktok | 🔴 heavy | OpenCLI + Chrome 扩展 | TikTok 国际版 (v0.7) |
| douyin | 🔴 heavy | OpenCLI fork + Chrome 扩展 | 抖音 (v0.7.2, 走 Daily-AC/OpenCLI fork) |
| 💎 tavily | booster | env `TAVILY_API_KEY` | 付费 (v0.4) |
| 💎 brave | booster | env `BRAVE_API_KEY` | 付费 (v0.4) |
| 💎 perplexity | booster | env `PERPLEXITY_API_KEY` | 付费 (v0.4) |
| 💎 exa | booster | env `EXA_API_KEY` | 付费 web search (v0.5) |
| wechat | ✅ ready | 无 (可选 `EXA_API_KEY` 增强) | 微信公众号 — search 走 Sogou 免费搜索 (`EXA_API_KEY` 可选启用语义增强); v0.10.1 起 `omnireach fetch <wechat-url>` 自动走 OpenCLI 登录态 Chrome 拿正文 |
| bilibili | ✅ ready | 无 (可选 `EXA_API_KEY` 增强) | B站 — v0.9 起默认走 B站官方 search API; `EXA_API_KEY` 可选启用语义增强 |

> **抖音 (douyin.com)** (v0.7.2): 走 `omnireach setup douyin`, 装 [Daily-AC/OpenCLI fork](https://github.com/Daily-AC/OpenCLI) (上游 PR [jackwener/OpenCLI#1759](https://github.com/jackwener/OpenCLI/pull/1759) 还在 review, 上游 merge + 发版后会切回 `@jackwener/opencli`)。需要在 Chrome 登录 www.douyin.com。`engagement.likes` 有真实数据 (DOM 抽取); `plays/comments/shares` 在搜索卡片上不暴露, 已 normalize 成 `null` 让下游 Agent 识别 unknown。

> **微信公众号 fetch** (v0.10.1): `omnireach fetch <mp.weixin.qq.com URL>` 走同一个 Daily-AC/OpenCLI fork (`weixin download --stdout`, 上游 PR [jackwener/OpenCLI#1770](https://github.com/jackwener/OpenCLI/pull/1770) 跟 #1759 同状态等 review)。需要在 Chrome 打开过任一 mp.weixin.qq.com 文章 (无显式 login step, 浏览器 cookies 已存)。详见下方 [如何取全文](#如何取全文-v08) 段。

> v0.4 及之前曾把 `web` 列为零配置, 实际不可用 (v0.1 起就是 architecture bug — 详见 `docs/superpowers/specs/2026-05-26-omnireach-v0.5-design.md`)。v0.5 起 web search 走 💎 exa booster (或任一付费 booster)。

## 升级

omnireach 还在 alpha 频繁迭代。检查 + 升级:

```bash
omnireach check-update                                                            # 比对 GitHub Releases
uv tool install --force git+https://github.com/Daily-AC/omnireach.git             # 拉最新
```

> ⚠️  `uv tool upgrade omnireach` **不会**拉新 commit (uv 把 git URL 装的工具锁在 install 时的 commit 上). `--force` 重装才会去 fetch 最新.

## 上游依赖

omnireach 不再在运行时调用任何 wrapper。每个 adapter 直接 shell 出对应上游 binary (yt-dlp / gh / rdt-cli) 或调用 Python 库 (feedparser)。每个 binary 用 `omnireach setup <X>` 引导安装。

一次性装齐 (可选, 不强制):

```bash
uv tool install git+https://github.com/Panniantong/Agent-Reach.git
agent-reach install --channels youtube,github,reddit
```

Agent-Reach 是上游 installer/doctor 工具, 完全可选 — omnireach 自己 doctor/search 都不依赖它。

## 🪟 平台支持

| 平台 | 状态 | 说明 |
|---|---|---|
| macOS | ✅ 主要开发平台 | 全部源测试过 (HN/RSS/youtube/github/reddit/twitter/xhs/tiktok/douyin + 4 booster + wechat/bilibili); `omnireach fetch` 三 backend (crwl/jina/opencli) 都跑过 |
| Linux | 🟡 best-effort | 应能 work；setup 流程对 `apt`/`pacman` 不自动 |
| WSL2 | 🟡 best-effort | 跟 Linux 一样 |
| Windows (原生 PowerShell) | 🟡 实验性 (v0.6.3+) | 代码已 macOS-假设解耦：secrets.env 不再调 POSIX chmod；preferences edit fallback notepad；setup github 提示加 `winget install GitHub.cli`；OpenCLI 类源 (twitter/xhs) 跨平台理论可用但未实测。**遇到问题请提 issue**。 |

跑 `omnireach doctor` 会在顶部打印一行 platform / Python 版本，方便提 issue 时附上。

## 💎 付费 booster (v0.4)

omnireach 默认完全免费。如果你愿意配置付费 API Key，结果质量会更高：

```bash
omnireach setup tavily       # 引导拿 Key + 写入 ~/.omnireach/secrets.env
omnireach setup brave
omnireach setup perplexity
omnireach setup exa          # v0.5 新增 (替代旧 web 源)
```

检测到 Key 后自动启用。结果元数据 `cost="paid"`，TTY 显示前缀 💎，便于审计。

要禁用：编辑 `~/.omnireach/preferences.toml` 设 `[boosters] auto_enable = false`。

## 📄 如何取全文 (v0.8)

omnireach 是 search 层, `content` 字段统一截到 ≤ 500 字 + `…`。Validator 在 contract 层（`SearchResult.content` pydantic field_validator）对**所有源**生效, 任何源的 content 超过 500 都会被截。这是有意为之 —— 全文留给未来 `omnifetch` 层处理 (见上方 [关于命名](#关于命名-omnireach-是工具集-suite-不是单一工具))。

对于上游本身就返全文的源 (wechat / exa / tavily) 或返长 thread 的源 (twitter), **完整原始 payload 保留在 `result.raw` 字典里**, Agent 想要全文时直接取:

```python
# Python (调用 CLI + 解析 JSON envelope)
import json
import subprocess

out = subprocess.run(
    ["omnireach", "search", "--json", "--on", "wechat", "claude 4.7"],
    check=True, capture_output=True, text=True,
)
env = json.loads(out.stdout)
snippet = env["results"][0]["content"]        # 500 字 + "…"
full    = env["results"][0]["raw"]["text"]    # Exa / wechat / twitter 全文
# tavily 对应 raw["content"]
```

```bash
# CLI + jq
omnireach search --json --on tavily "claude 4.7" | \
  jq '.results[] | {title, snippet: .content, full: .raw.content}'
```

字段对应表 (经 v0.8.1 + v0.9 真实 E2E 校正):

| 源 | `result.adapter` | `result.content` | `result.raw[...]` 取全文/原始 |
|---|---|---|---|
| wechat (默认 Sogou) | `sogou` | snippet (Sogou SERP 摘要) | `raw["item_html"]` (完整 Sogou 卡片 HTML) — 真要全文要进 mp.weixin.qq.com |
| wechat (EXA_API_KEY 启用) | `exa-api` | snippet | `raw["text"]` (Exa 全文) |
| bilibili (默认 B站 API) | `bilibili-api` | 视频 description (≤500) | `raw` 整个 video item dict, 含 desc/cover/aid/bvid |
| bilibili (EXA_API_KEY 启用) | `exa-api` | snippet | `raw["text"]` |
| exa | `exa-api` | snippet | `raw["text"]` |
| tavily | `tavily-api` | snippet | `raw["content"]` |
| twitter | `opencli` | snippet (长 thread 会触发截断) | `raw["text"]` |
| xiaohongshu | `opencli` | 空 — OpenCLI 搜索结果不含正文 | n/a (search 层无全文) |

`raw[...]` 的具体 key 名跟上游 API schema 直接对应, 上游若改 schema 这里也得跟着调；不确定可以先 `print(result.raw.keys())` 探一下。

其他源 (HN / GitHub / RSS / YouTube / 等) 的 content 一般 < 500 字, 多半 validator no-op, 但不保证 —— 真要全文兜底, 看 `result.raw` 有没有对应 key。

### 真要全文怎么办 → `omnireach fetch <url>` (v0.10+)

v0.10 起 `omnireach fetch <url>` 是 search → 全文 pipeline 的官方收敛形态, **host-aware** 自动选 backend:

```bash
# 任意网页 → crwl (本地 Crawl4AI) 优先, jina (r.jina.ai SaaS) fallback
omnireach fetch https://example.com/article --json

# 微信公众号 → 自动走 OpenCLI 登录态 Chrome (v0.10.1+), 绕过验证码
omnireach fetch https://mp.weixin.qq.com/s/<token> --json

# search → fetch pipeline 一气呵成
omnireach search --on wechat "claude 4.7" --json \
  | jq -r '.results[].url' \
  | xargs -I{} omnireach fetch --json {}
```

Backend 矩阵:

| URL host | `--backend auto` 走 | 备注 |
|---|---|---|
| `mp.weixin.qq.com` | **opencli** (登录态 cookie-strategy) | 装 [Daily-AC/OpenCLI fork](https://github.com/Daily-AC/OpenCLI) 拿 `weixin download --stdout` flag (v0.10.1 commit fe28823+); 直接 `crwl` / `jina` 会被微信"环境异常"验证码拦 |
| 其它 host | **crwl → jina** | Crawl4AI 优先, 失败/没装走 Jina Reader SaaS fallback |

显式 `--backend` 覆盖 auto:

| Flag | 行为 |
|---|---|
| `--backend crwl` | 强制走 Crawl4AI 本地 (66K ⭐ Apache-2.0, 内置 Cloudflare/Akamai/DataDome 反爬绕过) |
| `--backend jina` | 强制走 [Jina Reader](https://r.jina.ai/) SaaS — 零本地依赖, 免费额度大 |
| `--backend opencli` | 强制走 OpenCLI weixin 登录态路径 (仅 mp.weixin.qq.com 有意义) |

v0.10.1 给所有 backend 加 **CAPTCHA 启发式兜底**: 命中 `环境异常 / 完成验证后即可继续访问 / Cloudflare / Just a moment` 等关键词时, envelope `errors[]` 加一条 `captcha_suspected: ...`, markdown 字段保留 (graceful degrade — Agent 自己读 errors 决定信不信)。`omnireach doctor` 的 `wechat_backends` 段会 surface OpenCLI + `--stdout` 是否就绪。

## ⚙️ 用户偏好 (v0.4)

`~/.omnireach/preferences.toml` 可配置默认源、语言、输出格式、source_trust 覆盖。

```bash
omnireach preferences show     # 查看当前配置
omnireach preferences edit     # 用 $EDITOR 编辑
omnireach preferences reset    # 重置 (备份原文件到 .bak)
omnireach preferences path     # 打印文件位置
```

## 设计

详见 `docs/superpowers/specs/2026-05-25-omnireach-design.md`.

## License

MIT — 见 [LICENSE](LICENSE).
