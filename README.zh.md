# omnireach

<sub>[English](./README.md) · 中文</sub>

**你的 agent 读得了 Twitter，却读不了微信公众号。omnireach 解决这件事。**

omnireach 让你的 agent 搜索并读取登录墙后的中文互联网 —— 微信公众号 · 小红书 · 抖音 · B站 · TikTok —— 外加 Twitter、Reddit、HN、YouTube 等，统一接口：`omnireach search` 跨全部源返回同一套归一化 JSON schema，`omnireach fetch` 对任意 URL 返回干净 markdown。微信搜索**零配置**开箱即用 —— 无 key、无登录：

```bash
omnireach search --on wechat "Claude Code 技巧"   # 装完 60 秒内能跑
```

安装为 Claude Code Skill 后，下次会话 agent 自动就知道怎么用了。工具内部不调 LLM、重型源复用你自己的浏览器登录态，没有按次付费的爬取 API。

![demo — 零配置微信搜索, 跨源统一 JSON](./docs/assets/demo-wechat.gif)

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)

---

## 安装 —— 直接告诉你的 agent

> **「帮我安装 omnireach」**

你的 agent 会自动执行安装命令，你不需要复制任何东西。

<sub>手动备选 —— 如果你更喜欢自己粘贴到终端：</sub>

```bash
curl -fsSL https://raw.githubusercontent.com/Daily-AC/omnireach/main/install.sh | sh
```

这条命令会安装 CLI **并且**注册 Claude Code Skill（下次会话自动发现）。零配置源 —— HackerNews、RSS、微信（Sogou 路径）、B站 —— 立即可用。其他源各需一次性配置步骤。

---

## 你能得到什么

**1. 触达那些触达不了的地方。**
Twitter、Reddit、小红书、微信公众号、抖音、B站、TikTok —— 这些有登录墙的纵向平台，任何 agent 网络搜索都够不着。omnireach 通过你自己的已登录浏览器会话（借助 OpenCLI Chrome 桥接）读取这些平台，agent 看到的结果和一个已登录人类看到的一样。

**2. 统一的数据契约。**
`omnireach search` → 归一化 metadata + URL，跨所有源格式统一。`omnireach fetch` → 任意 URL 的干净 markdown，host 感知路由（`mp.weixin.qq.com` 走登录态 Chrome 绕过验证码；其他 host 走 Crawl4AI → Jina Reader 兜底）。Agent 只需学一套接口，不用对接 15 个 API。

**3. WebSearch 不可用时照样能搜。**
在 proxy / 中转站 / Bedrock / Vertex-Claude-3.x 等内置 WebSearch server tool 不可用的环境下，omnireach 在客户端直接实现搜索，绕过两层 gate，把搜索能力还给 agent。

---

## 和 Agent-Reach 有什么区别？

[Agent-Reach](https://github.com/Panniantong/Agent-Reach)（51k★）开创了这个品类，它做的事情它做得很好。omnireach 做的是另一组取舍 —— 以下是带日期戳的事实，不是营销话术：

| | omnireach | Agent-Reach（v1.5.0，截至 2026-07） |
|---|---|---|
| 微信公众号 | ✅ 零配置搜索（Sogou 路径）+ 登录态 Chrome 全文抓取 | ❌ 2026-06 整体删除（[PR #347](https://github.com/Panniantong/Agent-Reach/pull/347)，反爬失效） |
| 抖音 | ✅ 登录态 Chrome 搜索 | ❌ 2026-06 删除（上游工具已 archive） |
| TikTok | ✅ 搜索 | ❌ 从未支持 |
| 输出契约 | 全部 16 源统一 pydantic JSON schema；管道自动 JSON | 设计上无包装层 —— 各上游工具各自的格式（YAML / 纯文本 / 字幕文件 / 裸 JSON） |
| `search` / `fetch` 命令 | 内置 `omnireach search` + `omnireach fetch <url>`（host 感知路由） | 无 search/read 命令 —— 引导 agent 直接调各上游工具 |
| Facebook · Instagram · LinkedIn · 雪球 · 播客转录 | ❌ | ✅ |
| 社区 | 早期 —— 你比大部队先找到了这里 | 51k★，30 位贡献者 |

需要 Facebook/LinkedIn/转录，选 Agent-Reach。需要中文互联网（尤其微信）、机器稳定的 JSON 契约、或统一的 fetch 入口，这就是 omnireach 存在的原因。两者都是 MIT，在同一个 agent 里并存完全没问题。

---

## 示例

```bash
# 搜索有登录墙的纵向平台
omnireach search --on xiaohongshu --json "Claude Code 使用技巧"

# 抓取微信文章 —— 有登录墙，走你的浏览器会话
omnireach fetch --json "https://mp.weixin.qq.com/s/<token>"

# 完整流水线：搜索 → 批量抓全文
omnireach search --on wechat --json "claude 4.7" \
  | jq -r '.results[].url' \
  | xargs -I{} omnireach fetch --json {}
```

---

## 命令

| 命令 | 干嘛 |
|---|---|
| `omnireach search "<query>"` | 搜索 (SERP: metadata + URL) |
| `omnireach search --on twitter,reddit "..."` | 指定源 |
| `omnireach search --mode quick "..."` | 只查 HN |
| `omnireach search --mode deep "..."` | 查所有就绪源 |
| `omnireach search --json "..."` | 显式 JSON 输出 |
| **`omnireach fetch <url>`** (v0.10, v0.10.1) | **URL → 全文 markdown** — `mp.weixin.qq.com` 走 OpenCLI 登录态 Chrome (v0.10.1+), 其它 host 走 crwl → jina fallback |
| `omnireach fetch <url> --backend jina` | 强制走 Jina Reader SaaS (零本地依赖) |
| `omnireach fetch <url> --backend opencli` | 强制走 OpenCLI weixin 登录态路径 (v0.10.1+) |
| `omnireach init` | 写默认 `~/.omnireach/preferences.toml` |
| `omnireach sources` | 列出所有源 + 状态 |
| `omnireach setup <source>` | 引导式配置一个 🟡 / 🔴 源 |
| `omnireach doctor` | 健康检查 (含 sources / fetch backends / wechat backends) |

---

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
| wechat | ✅ ready | 无 (可选 `EXA_API_KEY` 增强) | 微信公众号 — search 走 Sogou 免费搜索; `EXA_API_KEY` 可选启用语义增强; v0.10.1 起 `omnireach fetch <wechat-url>` 自动走 OpenCLI 登录态 Chrome 拿正文 |
| bilibili | ✅ ready | 无 (可选 `EXA_API_KEY` 增强) | B站 — v0.9 起默认走 B站官方 search API; `EXA_API_KEY` 可选启用语义增强 |

> **抖音 (douyin.com)** (v0.7.2): 走 `omnireach setup douyin`，装 [Daily-AC/OpenCLI fork](https://github.com/Daily-AC/OpenCLI)（上游 PR [jackwener/OpenCLI#1759](https://github.com/jackwener/OpenCLI/pull/1759) 还在 review，merge 后切回）。需要在 Chrome 登录 www.douyin.com。`engagement.likes` 有真实数据（DOM 抽取）；`plays/comments/shares` 在搜索卡片上不暴露，已 normalize 成 `null`。

> **微信公众号 fetch** (v0.10.1): `omnireach fetch <mp.weixin.qq.com URL>` 走同一个 Daily-AC/OpenCLI fork（`weixin download --stdout`，上游 PR [jackwener/OpenCLI#1770](https://github.com/jackwener/OpenCLI/pull/1770) 同状态等 review）。需要在 Chrome 打开过任一 mp.weixin.qq.com 文章（无显式登录步骤，浏览器 cookies 已存）。详见下方「如何取全文」段。

---

## Agent 调用约定

作为 agent 调用 omnireach 时，**永远显式拿 JSON**，防止 rich 表格 wrap 让你抠不到字段：

```bash
# 方式 1：每条命令加 --json
omnireach search --json "..."
omnireach fetch  --json "<url>"

# 方式 2：env var（推荐给 agent harness 统一设）
export OMNIREACH_FORCE_JSON=1
```

v0.9.2 加的 `not isatty()` 自动 JSON 在大多数场景够用，但有些 agent 终端（如 Antigravity）给子进程分配真 PTY 让 `isatty()=True`，自动检测失效 —— 显式 `--json` 或 env var 是 always-works 保险。

完整 Skill 契约：[`.claude-plugin/skills/omnireach/SKILL.md`](./.claude-plugin/skills/omnireach/SKILL.md)

---

<details>
<summary><b>哪些人具体需要这个？（WebSearch 两层 gate 详解）</b></summary>

Claude Code 的 WebSearch 是**服务端 server tool**（`web_search_20250305`），真实可用性经过**两层独立 gate**：

**Gate 1 — 客户端 gate**（`WebSearchTool.isEnabled()` 看 `getAPIProvider()`）：
- 默认 `firstParty`（没设 `CLAUDE_CODE_USE_*` env var，包括只改了 `ANTHROPIC_BASE_URL` 的情况）→ tool **注册**
- 显式 `CLAUDE_CODE_USE_BEDROCK=1` → tool **关**
- 显式 `CLAUDE_CODE_USE_VERTEX=1` + Claude 4+ → 注册；老 Claude → 关
- 显式 `CLAUDE_CODE_USE_FOUNDRY=1` → 注册

**Gate 2 — 上游 server tool 实现 gate**：客户端把 tool schema 发出去后，上游 API 必须**专门实现** `web_search_20250305` 这个 server tool（接收 tool call → 跑搜索 → 返结果给客户端）：
- 真 Anthropic API (api.anthropic.com): ✓ 服务端原生跑
- Vertex / Foundry: ✓（各自 backend 实现了）
- **专门支持 Claude Code 的第三方模型厂**（e.g. DeepSeek 的 Anthropic-compat 端点）: ✓ 他们专门做了 server tool 处理，接到自己的搜索后端
- **OpenAI 兼容中转站**（cliproxy / anyrouter 等，把 Claude API → OpenAI Chat Completions 单纯转译）: ✗ 不识 server tool 这套语义
- **自托管 gateway / 大部分 proxy**: ✗ 一般不专门实现

Gate 2 看的是**「上游有没有专门做 Claude Code server tool 兼容」**，不是「是否真 Anthropic」。专门支持 Claude Code 的厂商（包括 DeepSeek，它不是真 Anthropic 但 WebSearch 工作）都实现了；单纯做 API 转译的中转站不实现。

**各常见痛点的根因不同**：
- 用 DeepSeek 等专门支持 Claude Code 的第三方：两层 gate 都过，WebSearch ✓ —— omnireach 对这群人的价值是补纵向源（Twitter/小红书/微信），不是补 search
- OpenAI 兼容中转站用户：客户端发了 tool，**上游没实现 server tool 处理** → 失败
- 显式 Bedrock 用户 / Vertex Claude 3.x 用户：客户端 `isEnabled` 就关

**就算你的 WebSearch 完全工作**，它也搜不全 —— Twitter 实时讨论 / Reddit 深度评论 / 小红书种草 / 微信公众号 / 抖音 / B站技术视频，这些登录墙纵向源服务端 WebSearch 几乎都够不着。omnireach 的三重价值：
1. 给客户端 gate 关掉的用户**补缺**
2. 给上游不实现 server tool 的用户**补缺**
3. 给 WebSearch 可用但搜不到纵向源的用户**补纵向**

</details>

<details>
<summary><b>关于命名与架构（search / fetch / parse 三层）</b></summary>

**omnireach** = `omni`（全部）+ `reach`（触达）。完整的「触达全网」语义需要三层能力，三层都将作为**本 repo 内的 sibling binary** 存在（类比 `cargo` / `rustc` / `rustfmt` 同 Rust repo 模式，**不开 sister repo**）：

| 层 | 实现 | 职责 | 状态 |
|---|---|---|---|
| **search** | `omnireach search` subcommand | 全网定位 — 返 metadata + URL，不取内容 | ✅ v0.7+ 在用 |
| **fetch** | `omnireach fetch` subcommand | 给定 URL 取全文 markdown — host-aware: `mp.weixin.qq.com` 走 OpenCLI 登录态，其它走 [Crawl4AI](https://github.com/unclecode/crawl4ai) → [Jina Reader](https://r.jina.ai/) | ✅ v0.10+（wechat 路径 v0.10.1+） |
| **parse** | （暂未实现，未来加在本 repo） | 视频/音频内容解析（字幕/STT/逐帧） | 🔜 未启动 |

v0.10 起 `omnireach` 同时负责 search + fetch 两层（subcommand 形式）。视频解析暂仍走 yt-dlp / whisper 等外部工具组合；parse binary 等真有用户需求才在本 repo 加（YAGNI，不开 sister repo）。

这样拆是有意为之——对照 Anthropic 自己的 [WebSearch](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-search) + [WebFetch](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-fetch) 拆分：每层 do one thing well，search 不被解析任务拖累延迟，Agent 调用方有自由组合空间。

> 曾考虑把 `omnireach` 改名 `omnisearch`，但 v0.10 落地 `omnireach fetch` subcommand 后该问题消解 —— `omnireach search`（触达 = 找）+ `omnireach fetch`（触达 = 取）都是 reach 的合理子动作，umbrella 名留给项目愿景。**不改名**（2026-05-27 确认）。

</details>

<details>
<summary><b>升级</b></summary>

omnireach 还在 alpha 频繁迭代。检查 + 升级：

```bash
omnireach check-update                                                            # 比对 GitHub Releases
uv tool install --force git+https://github.com/Daily-AC/omnireach.git             # 拉最新
```

> ⚠️ `uv tool upgrade omnireach` **不会**拉新 commit（uv 把 git URL 装的工具锁在 install 时的 commit 上）。`--force` 重装才会 fetch 最新。

</details>

<details>
<summary><b>平台支持</b></summary>

| 平台 | 状态 | 说明 |
|---|---|---|
| macOS | ✅ 主要开发平台 | 全部源测试过（HN/RSS/youtube/github/reddit/twitter/xhs/tiktok/douyin + 4 booster + wechat/bilibili）；`omnireach fetch` 三 backend（crwl/jina/opencli）都跑过 |
| Linux | 🟡 best-effort | 应能 work；setup 流程对 `apt`/`pacman` 不自动 |
| WSL2 | 🟡 best-effort | 跟 Linux 一样 |
| Windows（原生 PowerShell） | 🟡 实验性 (v0.6.3+) | 代码已 macOS 假设解耦：secrets.env 不再调 POSIX chmod；preferences edit fallback notepad；setup github 提示加 `winget install GitHub.cli`；OpenCLI 类源（twitter/xhs）跨平台理论可用但未实测。**遇到问题请提 issue。** |

跑 `omnireach doctor` 会在顶部打印一行 platform / Python 版本，方便提 issue 时附上。

</details>

<details>
<summary><b>💎 付费 booster (v0.4)</b></summary>

omnireach 默认完全免费。如果你愿意配置付费 API Key，结果质量会更高：

```bash
omnireach setup tavily       # 引导拿 Key + 写入 ~/.omnireach/secrets.env
omnireach setup brave
omnireach setup perplexity
omnireach setup exa          # v0.5 新增（替代旧 web 源）
```

检测到 Key 后自动启用。结果元数据 `cost="paid"`，TTY 显示前缀 💎，便于审计。

要禁用：编辑 `~/.omnireach/preferences.toml` 设 `[boosters] auto_enable = false`。

</details>

<details>
<summary><b>⚙️ 用户偏好 (v0.4)</b></summary>

`~/.omnireach/preferences.toml` 可配置默认源、语言、输出格式、`source_trust` 覆盖。

```bash
omnireach preferences show     # 查看当前配置
omnireach preferences edit     # 用 $EDITOR 编辑
omnireach preferences reset    # 重置（备份原文件到 .bak）
omnireach preferences path     # 打印文件位置
```

</details>

<details>
<summary><b>如何取全文 (v0.8)</b></summary>

omnireach 是 search 层，`content` 字段统一截到 ≤ 500 字 + `…`。Validator 在 contract 层（`SearchResult.content` pydantic `field_validator`）对**所有源**生效，任何源的 content 超过 500 都会被截。这是有意为之——全文留给 `omnireach fetch` 层处理。

对于上游本身就返全文的源（wechat / exa / tavily）或返长 thread 的源（twitter），**完整原始 payload 保留在 `result.raw` 字典里**，agent 想要全文时直接取：

```python
# Python（调用 CLI + 解析 JSON envelope）
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

字段对应表（经 v0.8.1 + v0.9 真实 E2E 校正）：

| 源 | `result.adapter` | `result.content` | `result.raw[...]` 取全文/原始 |
|---|---|---|---|
| wechat（默认 Sogou） | `sogou` | snippet（Sogou SERP 摘要） | `raw["item_html"]`（完整 Sogou 卡片 HTML）—— 真要全文要进 mp.weixin.qq.com |
| wechat（EXA_API_KEY 启用） | `exa-api` | snippet | `raw["text"]`（Exa 全文） |
| bilibili（默认 B站 API） | `bilibili-api` | 视频 description（≤500） | `raw` 整个 video item dict，含 desc/cover/aid/bvid |
| bilibili（EXA_API_KEY 启用） | `exa-api` | snippet | `raw["text"]` |
| exa | `exa-api` | snippet | `raw["text"]` |
| tavily | `tavily-api` | snippet | `raw["content"]` |
| twitter | `opencli` | snippet（长 thread 会触发截断） | `raw["text"]` |
| xiaohongshu | `opencli` | 空 —— OpenCLI 搜索结果不含正文 | n/a（search 层无全文） |

`raw[...]` 的具体 key 名跟上游 API schema 直接对应，上游若改 schema 这里也得跟着调；不确定可以先 `print(result.raw.keys())` 探一下。

其他源（HN / GitHub / RSS / YouTube 等）的 content 一般 < 500 字，多半 validator no-op，但不保证——真要全文兜底，看 `result.raw` 有没有对应 key。

### 真要全文怎么办 → `omnireach fetch <url>` (v0.10+)

v0.10 起 `omnireach fetch <url>` 是 search → 全文 pipeline 的官方收敛形态，**host-aware** 自动选 backend：

```bash
# 任意网页 → crwl（本地 Crawl4AI）优先，jina（r.jina.ai SaaS）fallback
omnireach fetch https://example.com/article --json

# 微信公众号 → 自动走 OpenCLI 登录态 Chrome（v0.10.1+），绕过验证码
omnireach fetch https://mp.weixin.qq.com/s/<token> --json

# search → fetch pipeline 一气呵成
omnireach search --on wechat "claude 4.7" --json \
  | jq -r '.results[].url' \
  | xargs -I{} omnireach fetch --json {}
```

Backend 矩阵：

| URL host | `--backend auto` 走 | 备注 |
|---|---|---|
| `mp.weixin.qq.com` | **opencli**（登录态 cookie-strategy） | 装 [Daily-AC/OpenCLI fork](https://github.com/Daily-AC/OpenCLI) 拿 `weixin download --stdout` flag（v0.10.1 commit fe28823+）；直接 `crwl` / `jina` 会被微信「环境异常」验证码拦 |
| 其它 host | **crwl → jina** | Crawl4AI 优先，失败/没装走 Jina Reader SaaS fallback |

显式 `--backend` 覆盖 auto：

| Flag | 行为 |
|---|---|
| `--backend crwl` | 强制走 Crawl4AI 本地（66K ⭐ Apache-2.0，内置 Cloudflare/Akamai/DataDome 反爬绕过） |
| `--backend jina` | 强制走 [Jina Reader](https://r.jina.ai/) SaaS —— 零本地依赖，免费额度大 |
| `--backend opencli` | 强制走 OpenCLI weixin 登录态路径（仅 mp.weixin.qq.com 有意义） |

v0.10.1 给所有 backend 加 **CAPTCHA 启发式兜底**：命中 `环境异常 / 完成验证后即可继续访问 / Cloudflare / Just a moment` 等关键词时，envelope `errors[]` 加一条 `captcha_suspected: ...`，markdown 字段保留（graceful degrade —— agent 自己读 errors 决定信不信）。`omnireach doctor` 的 `wechat_backends` 段会 surface OpenCLI + `--stdout` 是否就绪。

</details>

<details>
<summary><b>设计文档</b></summary>

详见 `docs/superpowers/specs/2026-05-25-omnireach-design.md`。

</details>

<details>
<summary><b>License</b></summary>

MIT —— 见 [LICENSE](LICENSE)。

</details>
