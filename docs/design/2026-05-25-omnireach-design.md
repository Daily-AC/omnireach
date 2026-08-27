# omnireach 设计文档

- **日期**: 2026-05-25
- **作者**: Daily-AC (张以琳)
- **状态**: Draft，待 §0 拍板后进入实现规划

## §0 一句话定义

**omnireach** 是一个 CLI + Claude Code Skill 双形态的「全网通」工具：为不能用 Anthropic 原生 WebSearch 的中转站 Agent 用户，一次性补齐 Web 搜索 + 多平台读取（Twitter / Reddit / YouTube / 小红书 / B站 / HN / GitHub / 微信公众号 / RSS 等）能力。

我们自己不写抓取代码 —— 由路由层、归一化层、引导式 onboarding 层组成的薄编排，把社区里已经成熟的三个上游工具（**Agent-Reach** / **OpenCLI** / **last30days**）当可插拔引擎调用。

## §1 背景与问题

中转站（cliproxy、anyrouter、各类 OpenAI 兼容代理）让国内同学绕过付费、调度多模型，但代价是丢失了 Anthropic 服务端工具，**WebSearch 是损失最重的一项**：

- Twitter / X 上的实时讨论：原生 WebSearch 几乎抓不到
- Reddit / HN 深度评论：拿不到
- YouTube 字幕、小红书种草、B站技术讨论：完全不可达
- 用户只能 `curl` + 自己解析 HTML，质量差又重复造轮子

社区已有解法：

- `Panniantong/Agent-Reach` ⭐20K — Python CLI，覆盖最全（13+ 平台）
- `jackwener/OpenCLI` ⭐22K — Node CLI + Browser Bridge，用登录态 Chrome 跑
- `mvanhorn/last30days-skill` ⭐26K — Claude Skill，跨源并发 + AI 综合打分

**问题**：三个 repo 形态不同、功能重叠又互补，普通用户挨个装、挨个配 wizard、挨个学命令名，劝退成本高。一个 query 该打哪几路、用哪个 repo 也没标准答案。

**omnireach 的位置**：把三者抽象成"引擎"，对外只暴露一个轻量 surface，做"装好就能搜全网"的承诺。

## §2 目标与非目标

### 目标 (v1)

1. 中转站用户用 `pipx install omnireach` 或 `/plugin install omnireach` **3 分钟内**有一个能搜全网的工具
2. 首次启动后零配置可用 ≥ 7 个源（web / YouTube / HN / RSS / GitHub / 微信公众号 / B站）
3. 单一 query 入口，路由层自动决定打哪几路 + 用户可 `--on` 覆盖
4. **Agent 能自动做的事一律 Agent 做**：装依赖、跑 doctor、写配置文件、刷新缓存。只在「人脸/扫码/装浏览器扩展/给 API Key」这种 Agent 无法做的节点才停下来问用户
5. 输出 JSON 契约稳定，下游 Agent / pipeline / Skill 都能消费
6. 中文 first，README 同步英文译本

### 非目标 (v1)

- **不重新实现抓取**：所有数据获取由上游引擎完成。我们只做"翻译"和"编排"
- **不自建付费 API**：付费源（Tavily/Brave/Perplexity/SerpAPI）仅在用户已有 Key 时作为 booster 接入
- **不做 RL 训练/智能 ranking 模型**：v1 用规则评分（来源权重 × 互动量 × 新鲜度）
- **不做浏览器自动化框架**：复杂登录场景委托 OpenCLI，我们只是调度它
- **不做 UI**：CLI / Skill 文本输出即终态，不做 web GUI / TUI dashboard

## §3 甲方决策（已锁定）

| 项 | 决定 | 备注 |
|---|---|---|
| 项目名 | **omnireach** | CLI 命令、repo 名、Skill 触发词统一 |
| 付费源 | **免费优先 + 可选付费增强** | `0 Key 0 元`是默认承诺，付费 Key 仅作 booster |
| 主语言 | **中文 first，英文 README 副本** | wizard / CLI 输出走中文 |
| Repo 归属 | `github.com/Daily-AC/omnireach`（个人账号） | MIT license（与三家上游兼容） |
| 整合路线 | **Umbrella + 适配器壳**（A 方案） | 上游工具按需 `pipx install` / `npm i -g` |
| 路由模型 | **默认自动 + `--on` 覆盖**（C 方案） | |
| Onboarding | **分层 + 心愿单**（C 方案） | `omnireach sources` 显式 surface |

## §4 用户旅程

### 4.1 首次安装（中转站同学典型流）

```
$ pipx install omnireach
$ omnireach init
  ✨ omnireach v0.1.0
  正在自动配置零配置的源…
   ✅ web search (Jina Reader, 免费)
   ✅ youtube (yt-dlp, 已自动安装)
   ✅ hackernews (public JSON)
   ✅ rss
   ✅ github (gh CLI 已检测到)
   ✅ 微信公众号
   ✅ B站（本地直连可用，海外/服务器需配代理）
  完成。现在试试：  omnireach "Claude 4.7 怎么样"

  其它 3 个源需要配置才能用，运行 `omnireach sources` 查看心愿单。
```

### 4.2 日常搜索

```bash
omnireach "Claude 4.7 prompt caching 实测"
# 自动 fanout 到: web + hackernews + reddit (若已配) + youtube + github

omnireach --on twitter,reddit "anyrouter 跑路"   # 显式指定
omnireach --json "..." | jq '.results[] | .url'    # 管道下游
```

### 4.3 解锁新源（引导式）

```
$ omnireach sources

  ✅ ready (7):    web, youtube, hackernews, rss, github, 微信公众号, B站
  🟡 一步配置 (1):  reddit
  🔴 重配置 (2):    twitter, 小红书

$ omnireach setup reddit
  Reddit 需要登录态（rdt-cli）。
  Agent 能做的：
   ✅ 安装 rdt-cli (npm i -g)
   ✅ 启动登录流程
  你需要做的：
   👤 在浏览器里完成 Reddit OAuth 授权（30 秒）
  开始吗? [Y/n]
```

`setup` 子命令是**对话式的**：每一步 Agent 都先尝试自动做，做不了的明确告诉用户"轮到你了，做这一步"，做完回车继续。

## §5 架构

```
                      ┌────────────────────────────────┐
                      │  Entry: CLI  /  Skill manifest │
                      │  (omnireach / /omnireach)      │
                      └───────────────┬────────────────┘
                                      │  query, flags
                                      ▼
                  ┌───────────────────────────────────────┐
                  │           Core                        │
                  │   Router → Dispatcher (并发 fanout)   │
                  │   Source Registry (心愿单)            │
                  │   Onboarding Wizard                   │
                  │   Normalizer / Scorer                 │
                  └───────────────────────────┬───────────┘
                                              │  SearchResult[]
                          ┌───────────────────┼────────────────────┐
                          ▼                   ▼                    ▼
                   ┌──────────────┐    ┌──────────────┐   ┌──────────────┐
                   │ AdapterShell │    │ AdapterShell │   │ AdapterShell │ …
                   │  (web)       │    │  (twitter)   │   │  (reddit)    │
                   └──────┬───────┘    └──────┬───────┘   └──────┬───────┘
                          │ subprocess        │ subprocess       │ subprocess
                          ▼                   ▼                  ▼
                   agent-reach            opencli            agent-reach
                   (Jina / MCP)        (logged Chrome)        (rdt-cli)
```

### 5.1 组件职责

| 组件 | 职责 | 估算 LoC |
|---|---|---|
| **CLI Entry** (`omnireach/__main__.py`) | argparse + 子命令分发（`search` / `init` / `sources` / `setup` / `doctor`） | ~200 |
| **Skill manifest** (`.claude-plugin/skills/omnireach/SKILL.md`) | 触发说明 + 单行 shell out 到 CLI | ~50 |
| **Source Registry** (`registry.py` + `sources.yml`) | 单一真相源：每个 source 的 id / adapter / 状态 / 依赖 / 引导步骤 | ~400 |
| **Router** (`router.py`) | 根据 query 关键词 + flags 决定打哪几路（启发式规则，非 ML） | ~250 |
| **Dispatcher** (`dispatcher.py`) | 并发 fanout、单源超时、错误隔离 | ~200 |
| **Adapter Shells** (`adapters/*.py`) | 每个 source 一个文件，subprocess 调上游 + 解析输出 | 每个 ~150 |
| **Onboarding Wizard** (`wizard.py`) | 对话式引导，区分"Agent 做"和"用户做" | ~500 |
| **Normalizer / Scorer** (`scoring.py`) | 统一 schema + 规则打分排序 | ~150 |

**总计预算**: 核心 ~2k LoC，10 个 adapter ~1.5k LoC，**目标 < 5k LoC**。

### 5.2 SearchResult 契约

```json
{
  "query": "...",
  "ts": "2026-05-25T12:50:00Z",
  "results": [
    {
      "source": "twitter",           // 哪一路
      "title": "...",
      "url": "https://...",
      "content": "...",              // 已抓取/已清洗的正文或摘要
      "author": "...",               // 可选
      "score": 0.87,                 // 规则评分 (0..1)
      "engagement": {                // 可选，源相关的互动指标
        "likes": 1234,
        "comments": 56
      },
      "ts": "...",                   // 内容发布时间
      "adapter": "agent-reach",      // 哪个上游产出
      "raw": { "...": "..." }        // 原始字段，下游需要可读
    }
  ],
  "errors": [
    { "source": "reddit", "error": "rdt-cli not authenticated" }
  ]
}
```

### 5.3 Source Registry 数据形态

```yaml
# sources.yml
- id: twitter
  adapter: opencli   # 默认走 OpenCLI（登录态 Chrome），可 fallback agent-reach
  fallback_adapter: agent-reach
  status_check: opencli twitter state
  deps:
    auto:                                    # Agent 自动装
      - { kind: npm, name: "@jackwener/opencli" }
      - { kind: chrome_extension, source: "https://chrome.google.com/...", manual: true }
    manual:                                  # 必须用户做
      - { step: "在 Chrome 登录 Twitter 账号", verify: "opencli twitter state | jq .ok" }
  search:
    cmd: "opencli twitter search --json --limit {limit} {query}"
  query_hints: ["twitter", "x.com", "推特"]   # router 看到这些词加权
```

Wizard 读这份配置就能完整驱动 setup；Router 读 `query_hints` 决定要不要 fanout 到此源。

## §6 v1 source 覆盖

| Source | 状态 | 适配器 | 依赖 | 配置工作 |
|---|---|---|---|---|
| web | ✅ ready | agent-reach | Jina Reader + MCP | 无 |
| youtube | ✅ ready | agent-reach | yt-dlp | 无 |
| hackernews | ✅ ready | 自带（用 HN JSON API） | — | 无 |
| github | ✅ ready | agent-reach | gh CLI（已登录的话） | 无 |
| rss | ✅ ready | agent-reach | feedparser | 无 |
| 微信公众号 | ✅ ready | agent-reach | — | 无 |
| B站 | ✅ ready（本地） | agent-reach | — | 海外/服务器场景需配代理（一步） |
| reddit | 🟡 一步 | agent-reach | rdt-cli | OAuth 一次 |
| twitter | 🔴 重 | opencli | Chrome 扩展 + 登录态 | 装扩展 + 登录 |
| 小红书 | 🔴 重 | opencli | Chrome 扩展 + 登录态 | 装扩展 + 登录 |

v2+ 候选：抖音、LinkedIn、TikTok、Polymarket、Threads、Pinterest、Bluesky、Perplexity（付费 booster）。

## §7 路由策略（启发式）

Router 不是 ML，是简单规则栈：

1. 若有 `--on src1,src2`，跳过自动选源
2. query 命中 `query_hints` 的源加入候选
3. 没有命中任何 hints 时，走"默认全网"组合：`web + hackernews + github + youtube + reddit`（若就绪）
4. 用户偏好（`~/.omnireach/preferences.toml` 中的 `default_sources`）覆盖默认
5. 候选源数 > 5 时砍掉互动量最低权重的源（避免噪音）

`--mode quick`（只 web + hn）、`--mode deep`（全部 ready 源）作为快捷开关。

## §8 引导式 Wizard 设计

### 8.1 Agent 能做的 vs 用户做的

| Agent 自动 | 必须用户 |
|---|---|
| 装 npm / pipx 包 | 完成 OAuth 浏览器跳转 |
| 写配置文件 | 扫码登录（小红书/微信/抖音）|
| 跑 doctor 自检 | 装 Chrome 扩展（点 chrome://extensions）|
| 解析 JSON / 重试 | 给付费 API Key（仅 booster 场景）|
| 调试错误并自动修复 | 商业关系判断（"要不要给这个站 cookie"）|

### 8.2 对话节奏

每个 setup 步骤遵循同一句式：

```
[源名] 还差: <一句话说差什么>
Agent 能做的:
  ✅ <步骤 1>
  ✅ <步骤 2>
你需要做的:
  👤 <一行人话指令>  (预计 <时间>)

开始吗? [Y/n]
```

回车继续。`verify` 命令自动跑，挂了 wizard 重试或退出，**绝不静默失败**。

## §9 分发渠道

1. **PyPI**：`pipx install omnireach` —— 主分发
2. **Claude Code Marketplace**：`/plugin marketplace add Daily-AC/omnireach` —— Skill 触发入口
3. **npm（薄壳）**：可选，给习惯 Node 生态的用户一条 `npx omnireach` 等价路径（直接 spawn pipx 版本，避免双实现）
4. **直接 git clone + `make install`**：给离线/受限网络用户

Skill 安装路径示意：

```
.claude-plugin/
└── skills/
    └── omnireach/
        ├── SKILL.md           # 触发说明 + 单行 exec
        └── ASSETS/             # 心愿单截图等
```

## §10 错误处理

- **单源失败不影响整体**：dispatcher 用 `asyncio.gather(return_exceptions=True)`，错误归到 `result.errors[]`
- **超时**：每源默认 15s，可配置；超时不阻塞 normalizer
- **上游 CLI 缺失**：第一次调用某 adapter 时检查二进制存在，缺则触发 wizard 引导而非崩溃
- **认证过期**：返回错误码 `AUTH_EXPIRED`，CLI 提示 `omnireach setup <src> --renew`
- **限流**：尊重上游退避策略，本地 ratelimit (`tenacity`) 兜底
- **绝不静默**：所有失败必须出现在 `errors[]` 或 stderr 中

## §11 测试策略

- **契约测试**：对每个 adapter 喂固定 fixture（cassette），断言归一化输出符合 SearchResult schema
- **集成测试**：少量真实网络的 smoke test，标记 `@pytest.mark.live`，CI 默认跳过
- **Wizard 重放测试**：用 expect/pexpect 录制对话脚本，回放断言
- **Source Registry lint**：CI 阶段校验 `sources.yml` 字段完整性 + 引用的命令存在
- **覆盖率目标**：核心 (router/dispatcher/normalizer) ≥ 80%，adapter shell ≥ 50%（因主要逻辑在上游）

## §12 路线图

| 阶段 | 范围 | 衡量 |
|---|---|---|
| **v0.1** | Core + 5 个零配置源（web/youtube/hn/github/rss）+ CLI + Skill manifest | `pipx install` 后 `omnireach "..."` 能出结果 |
| **v0.2** | 解锁 reddit / 微信公众号 / B站 + 引导式 wizard 完整化 | `omnireach setup <src>` 全跑通，doctor 全绿 |
| **v0.3** | twitter / 小红书 via OpenCLI + Chrome 扩展引导 | 验证登录态 adapter 路径 |
| **v0.4** | 付费 booster（Tavily/Brave/Perplexity 检测式接入）+ 评分模型小改 | 用户给 Key 后结果质量明显提升 |
| **v1.0** | 文档定稿、英文 README、Claude Marketplace 上架 | 公开发布、star/issue 通道 |

## §13 风险与开放问题

| 风险 | 缓解 |
|---|---|
| 上游 CLI 接口变化 | adapter shell 隔离；CI 跑 contract test 早发现 |
| 上游 repo 弃维护 | 适配器解耦，可平滑切换到 fallback adapter 或自实现 |
| 平台反爬升级（小红书/B站） | OpenCLI 用真实登录态 Chrome，理论最难封；warning 用户预期 |
| 用户多机器同步登录态 | v1 不解决；文档建议每台机器各跑一次 setup |
| Claude Skill 接口可能变化 | SKILL.md 跟随 Anthropic 最新规范，每季度校验 |
| 法律 / TOS | 公开声明仅供个人研究学习；不爬取付费墙后内容；遵守 robots.txt |

## §14 决策追踪

| 决策 | 选项 | 选定 | 理由 |
|---|---|---|---|
| 产品形态 | Skill / CLI / 两者 | **两者** | 用户首次访问通过 Skill，深度使用走 CLI |
| 范围 | WebSearch 平替 / 互联网能力包 / 分阶段 | **互联网能力包** | 用户痛点（Twitter）不只是 web 搜索 |
| 路由 | 显式 / 自动 / 自动+覆盖 | **自动+覆盖** | 中转站同学不熟悉源名 |
| Onboarding | 上来全配 / 懒加载 / 分层心愿单 | **分层心愿单** | 入门 30 秒 + 自主扩能力 |
| 整合路线 | umbrella / submodule / 重写 | **umbrella + 适配器壳** | 最轻、解耦最干净 |
| 项目名 | omnireach / wanglai / pansou | **omnireach** | 国际化 + 品牌感 |
| 付费源 | 免费 / 免费+可选付费 / 付费档 | **免费+可选付费** | 0 Key 0 元承诺保留，质量天花板可拔 |
| 主语言 | 中文 first / 英文 first / 双语 | **中文 first** | 用户群现实 |
