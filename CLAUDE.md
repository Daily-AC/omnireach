# CLAUDE.md — omnireach 项目协作上下文

This file is loaded automatically when Claude Code starts in this repo. It carries omnireach project knowledge that previously lived in user-global memory; centralizing it here lets the context follow the repo across machines and sessions.

## 项目是什么

**omnireach 是项目名, 同 repo 内多个职责子命令 (subcommand 形态, 落地后再判断要不要拆 binary)**, 不是单一工具。完整"触达全网"语义由三层职责实现, 都在同 repo（**不开 sister repo**, 拍板于 2026-05-27 session）:

- **`omnireach search`** (v0.1+ 起在用): search 层 — 全网定位 metadata + URL, **不取内容**
- **`omnireach fetch`** (v0.10 起 ship 为 subcommand): fetch 层 — 给定 URL 取全文 markdown; 当前 host-aware 路径为普通网页内置 HTTP → Jina fallback，`mp.weixin.qq.com` → OpenCLI 后台临时 tab；Crawl4AI 只保留显式 opt-in
- **parse** (暂未实现): parse 层 — 视频/音频内容解析 (字幕/STT/逐帧), 真有 issue 才加

类比 `cargo` (一个 repo 下 `cargo` / `rustc` / `rustfmt` 多个 sibling binary, 共享一个项目愿景) 而不是 `git` + `git-lfs` (后者是 standalone separate repo)。**Why monorepo 而非 multirepo**: 2026-05-27 session 调研 Crawl4AI 时验证 —— 收纳 `crwl` 作为 fetch 工具不影响 search 行为, 只补齐 search 结果, 完全没有 sister repo 的耦合协调成本。一个 release 频道 + 一个 issue tracker + 一份 README 就够。

**search binary 名是否改名**: ~~曾经考虑改成 `omnisearch` 因为"reach 是触达, search 只是触达的第一步"~~ — **2026-05-27 拍板不改**。Rationale: v0.10 ship 了 `omnireach fetch` 后, `omnireach` 这个名字反而契合 umbrella 定位 —— `omnireach search` (触达 = 找) + `omnireach fetch` (触达 = 取) 都是 reach 的合理子动作, subcommand 分担具体语义, 项目名留给愿景。改名得不偿失。

本 repo 当前覆盖 search (v0.1+) + fetch (v0.10+) 两层。用户问"加 parse 能力到 omnireach 里"时按"等本 repo 加 sibling subcommand/binary, 不开 sister repo"处理; 视频解析这类大依赖立项前先看真 issue (YAGNI)。见下方"架构边界"。

## 目标用户与痛点

omnireach 是给**任何 Claude Code WebSearch 拿不到结果**的用户的工具 — 受众比"中转站"宽得多。

**WebSearch 是 server tool** (`web_search_20250305`), 真实可用性其实经过**两层 gate**, 受影响场景**不同根因不同**:

**1. 客户端 gate** (`WebSearchTool.isEnabled()` + `getAPIProvider()` 看 `CLAUDE_CODE_USE_*` env var):
- 默认 `firstParty` (没设 `CLAUDE_CODE_USE_*`, 即便只改了 `ANTHROPIC_BASE_URL` 也归这类) → tool 注册
- 显式 `CLAUDE_CODE_USE_BEDROCK=1` → 关
- 显式 `CLAUDE_CODE_USE_VERTEX=1` + Claude 4+ → 注册; 老 Claude → 关
- 显式 `CLAUDE_CODE_USE_FOUNDRY=1` → 注册

**2. 上游 server tool 实现 gate** (上游 API 必须**专门实现** `web_search_20250305` server tool — 即接 tool call → 跑搜索 → 返结果给客户端):
- 真 Anthropic (api.anthropic.com): ✓ 原生实现
- Vertex / Foundry 支持的 model: ✓ 各自 backend 实现了
- **专门支持 Claude Code 的第三方模型厂** (e.g. DeepSeek 的 Anthropic-compat 端点): ✓ 他们专门做了 server tool 处理, 接到自己的搜索后端 (data point: 2026-06-03 user 实测)
- **OpenAI 兼容中转站** (cliproxy / anyrouter 等, 把 Claude API → OpenAI Chat Completions 单纯转译): ✗ 不识 server tool 语义
- **自托管 gateway / 大部分 proxy**: ✗ 一般不专门实现

**关键 insight**: 上游 gate 看的是**"上游有没有专门做 Claude Code server tool 兼容"**, 不是"是否真 Anthropic"。专门支持 Claude Code 的厂商都实现; 单纯做 API 转译的不实现。"上游不是真 Anthropic 所以 fail" 这个 framing 是错的 (e.g. DeepSeek 不是真 Anthropic 但 WebSearch 工作)。

**分场景痛点根因**:
- 用 DeepSeek 等专门支持 Claude Code 的第三方: 两层 gate 都过, WebSearch ✓ — **omnireach 对这群人价值是补纵向源 (Twitter/小红书/微信), 不是补 search**
- OpenAI 兼容中转站用户: **上游没实现 server tool 处理** → 失败
- 显式 Bedrock 用户 / Vertex Claude 3.x: 客户端 isEnabled 直接关

**Why omnireach 不止补缺**: 即使 WebSearch 可用 (firstParty 直连), 它也搜不全 — Twitter / Reddit / 小红书 / 微信公众号 / 抖音 / B站 / TikTok 这些纵向源服务端 WebSearch 几乎都够不着。omnireach 三重价值: (1) 给客户端 gate 关掉的用户**补缺**; (2) 给上游不实现 server tool 的用户**补缺**; (3) 给 WebSearch 可用但搜不到纵向源的用户**补纵向**。CLI + MCP + Claude Code Skill 三形态。

**历史措辞修订 (2026-06-03 三轮)**:
- 第一轮 (上午): README/SKILL/本文件痛点写"中转站丢 WebSearch" — narrow
- 第二轮 (今晚 23:00): 把根因改成"Claude Code 客户端 `isEnabled()` allowlist" — 错, 因为 `isEnabled()` 看的是 `CLAUDE_CODE_USE_*` env var, 不是 `ANTHROPIC_BASE_URL`, 中转站用户实际 isEnabled=true
- 第三轮 (今晚 23:30): 拆成两层 gate, 客户端 + 上游, 上游说"必须是真 Anthropic" — 错, 因为 DeepSeek 不是真 Anthropic 但 WebSearch 工作
- 第四轮 (现在 23:44): 上游 gate 准确说法是**"是否专门实现 server tool"**, 跟"是否真 Anthropic"无关。DeepSeek 等专门支持 Claude Code 的第三方都实现; 单纯 API 转译的中转站不实现。这才是准确的。

- 位置: `~/Projects/omnireach`
- GitHub: https://github.com/Daily-AC/omnireach (Public, MIT, 归属 Daily-AC)

## 架构核心 — Umbrella + 适配器壳（v0.5 修订）

- 上游 binary 直调: `yt-dlp` (youtube) / `gh` (github) / Python `feedparser` (rss)
- OpenCLI bridge (Node + 登录态 Chrome) → reddit / twitter / xiaohongshu / tiktok / douyin
- Application services: `omnireach.service.search` + `omnireach.fetcher.fetch`，CLI 与 MCP 共用同一 envelope 和 backend 逻辑
- MCP stdio: `omnireach mcp` 零新增依赖实现 MCP 2025-06-18，暴露 `omnireach_search` / `omnireach_fetch`
- HN 直接调 Algolia Search API（无上游）
- Boosters (Tavily / Brave / Perplexity / Exa) → httpx 调付费 API，env var 检测式接入
- Agent-Reach **完全可选**（v0.5 起）: 仅作 `setup --batch` 一键引导 installer，runtime 不依赖

omnireach 自己只做: 路由 (Router) + 并发分发 (Dispatcher) + 归一 (Normalizer/Scorer) + 引导 (Wizard) + 标准化 JSON 契约 (SearchResult/SearchEnvelope, pydantic v2)。

## Tier 系统 (5 tier, sources.yml 中声明)

- ✅ `ready`: 零配置或一条 `pip install` 可用 (HN/youtube/github/rss)
- 🟡 `one_step`: 一次 OAuth/Key 配置
- 🔴 `heavy`: 装 Chrome 扩展 + 浏览器登录态 (reddit / twitter / xiaohongshu / tiktok / douyin)
- 💎 `booster`: 付费 API Key (Tavily/Brave/Perplexity/Exa)，env var 检测，结果元数据 `cost="paid"`
- 🚧 `wip`: 待重写源，sources 列表显示但不参与 auto fanout (v0.7 起暂无 wip 源)

## 架构边界 (v0.7 拍板三层职责, 2026-09-03 按已发布事实修订)

对照 Claude Code 的 WebSearch + WebFetch 拆分，omnireach 是三层架构里的最上层:

```
omnireach    → 多源 WebSearch (返 metadata + URL, 不取内容)        ← 本 repo
omnifetch    → 多源 WebFetch (给定 URL 取全文 markdown)              ← 未来 sister repo
omniparse    → 视频/音频专项 fetch (字幕/STT/逐帧)                    ← 未来 sister repo
```

**Why**: search vs parse 是不同职责。把解析塞进 search 会让边界变模糊、token 爆炸、违反"do one thing well"。Claude Code 自己 WebSearch + WebFetch 就是这么拆的; OpenAI Codex 走相反路线 (单 `web_search` 黑箱), 我们不抄。

**架构边界的当前形态** (2026-09-03 按已发布事实重写; 此前版本禁止 parse/download 子命令, 与 v0.17/v0.18 已 ship 的现实冲突):

三层职责仍然成立, 但**三层都在本 repo, 以 subcommand 形态并存** (monorepo + sibling subcommand, 不开 sister repo):

- `omnireach search` — 定位 metadata + URL
- `omnireach author` — 某个创作者本人的作品目录 (v0.19 起; 仍是 search 层语义: 返 metadata + URL, 不返内容)
- `omnireach fetch` — 给定 URL 取全文 markdown
- `omnireach media inspect|parse|download` — 视频/音频元数据、字幕产物、有界下载 (v0.17/v0.18)

**仍然是硬边界, 违反就拒绝**:

- 不要在 adapter 里跑 LLM call 做 summary (会引入 LLM 依赖, 让工具从「纯多源汇聚 + 零 LLM 依赖」变成「小 Agent + LLM key 必需」)
- search 层的 `SearchResult.content` 统一截到 500 字 snippet (v0.8 起由 contract 层 `field_validator` 强制), 全文留在 `result.raw`
- **视频直链 mp4 CDN 默认不进 search 层 envelope**。`omnireach author --include-media-urls` / `include_media_urls: true` 是唯一出口, **默认关**, 2026-09-03 甲方复核后维持; 打开时直链只进 `result.raw.play_url`, 且它带 `x-expires` 签名会过期。要文件走 `omnireach media download`。
- 浏览器凭据 (cookie / profile 名 / 签名 URL) 永远不进 envelope、manifest 或任何落盘产物
- 用户问「加 X 功能」时先判断 X 属于 search / author / fetch / media 哪层; 都不属于就说清楚它是新的一层, 由甲方决定要不要开

**~~当前违规~~已修** (v0.8 修复): 4 个长文本源 (wechat/xiaohongshu/exa/tavily) 在 `SearchResult.content` 上的全文塞入由 contract 层 `field_validator` 截到 500 字 + "…"; 全文保留在 `result.raw` 中。见 `docs/design/2026-05-27-omnireach-v0.8-design.md`。

**为什么 v0.8 不抄 Claude Code 的 LLM-summarized snippet**: Claude Code 用 sub-LLM (Haiku) 压缩 snippet 是因为 user-facing 直接看; omnireach 用户 = Agent (本身就是 LLM), 拿到截断 raw 自己能消化, 不需要 omnireach 替它压缩。抄了反而让 omnireach 从"纯多源汇聚 + 零 LLM 依赖"变成"小 Agent + LLM key 必需", 边界模糊化。

**fetch 状态** (2026-05-27): v0.10 已 ship 为 `omnireach fetch <url>` subcommand, v0.10.1 加 host-aware routing 让 `mp.weixin.qq.com` 走 OpenCLI 登录态。**parse 启动时机**: 等用户提"我要视频/音频内容解析"真 issue 再在本 repo 加 subcommand 或新 binary (YAGNI), **不开 sister repo**。

## 已发布版本

- `v0.1.0-alpha`: core 架构 + 7 ready 源 (web / HN / YouTube / GitHub / RSS / 微信公众号 / B站) + Skill manifest
- `v0.2.0-alpha`: 对话式 wizard + reddit (🟡 one_step) + HN→Algolia API + --on 拼错警告
- `v0.3.0-alpha`: twitter + xiaohongshu via OpenCLI (🔴 heavy) + wizard verify 回环
- `v0.4.0-alpha`: 付费 booster (Tavily/Brave/Perplexity 💎) + `~/.omnireach/preferences.toml` 用户偏好层 + source_trust 加权 ranking (0.4·recency + 0.6·trust) + 💎 TTY 前缀；124 tests
- `v0.5.0-alpha`: **架构 bug 修复** —— v0.1 起 6 个 wrapper adapter 调用的 `agent-reach <source> search` 子命令不存在 (真实 Agent-Reach 是 installer 不是 search proxy)。重写为直调上游 binary, web 降级 booster (Exa), wechat/bilibili 标 🚧 wip。setup/doctor 全部重写。155 tests
- `v0.5.1-alpha`: `omnireach check-update` 子命令 (调 GitHub Releases API 比对本地 `__version__`) + README 升级章节
- `v0.5.2-alpha`: **opencli adapter contract hotfix** —— twitter/xiaohongshu adapter `--json` → `--format json`; opencli 返回 array 不是 dict; 默认 timeout 15→30s。163 tests
- `v0.6.0-alpha`: wechat/bilibili 从 🚧 wip 升级到 💎 booster (Exa domain-filtered, 共享 EXA_API_KEY); per-source `timeout_seconds`; dispatcher 错误分类 (`AdapterUnavailable` silent in TTY, failed → ✗ red); `scripts/verify-adapter-contracts.sh` 防 argv drift。183 tests
- `v0.6.1-alpha`: hotfix `omnireach init` 不再 `pipx install agent-reach` (死代码)。185 tests
- `v0.6.2-alpha`: `.github/ISSUE_TEMPLATE/` × 4 (YAML form) + TTY failed errors 加 issue link footer + 全局 `_entrypoint()` 异常 wrapper。190 tests
- `v0.6.3-alpha`: Windows hardening (4 处 macOS-假设解耦) + `doctor` 顶部 platform info 行。198 tests。**无 Windows 测试机器，等真实用户反馈**
- `v0.7.0-alpha` (2026-05-26): **tiktok** (🔴 heavy) — TikTok 国际版视频搜索, 走 OpenCLI 登录态 Chrome, pattern 同 twitter/xiaohongshu。204 tests。PR #13
- `v0.7.1-alpha` (2026-05-26): **hotfix tiktok 字段映射** — engagement 字段名是猜的, 真实 opencli output 是 plays/likes/comments/shares 而非 play_count/digg_count 等, 用户拿到的 engagement 全 None。E2E 修正后实测 likes=1291/views=24500。PR #14
- `v0.7.2-alpha` (2026-05-26): **douyin via OpenCLI fork** — 不等上游, omnireach 切到 [Daily-AC/OpenCLI fork](https://github.com/Daily-AC/OpenCLI)。OpenCLI 系 4 源全切 fork; 上游 merge 后切回, adapter 不动。`plays/comments/shares` zero→None normalize (DOM 卡片只暴露 likes)。E2E 实测 likes=40000。PR #15, **closes issue #12**。209 tests
- `v0.8.0-alpha` (2026-05-27): **架构修复** — `SearchResult.content` 在 contract 层 (pydantic `field_validator`) 强制截到 500 字 + "…"; 全文保留在 `result.raw` (4 个长文本源 wechat/xhs/exa/tavily 上游 payload 本就存了)。零 adapter 改动, 单一实现点防未来 adapter 漂移。218 tests。PR #18
- `v0.8.1-alpha` (2026-05-27): **xhs adapter 字段映射 hotfix** — 真 E2E 时发现 OpenCLI v1.7.22+ 真实 xhs 输出 key 是 `likes(string)/title/url/published_at/rank/author/author_url`, 没有 `content / like_count / comment_count / collect_count`。adapter 自 v0.5.2 起就在猜 key 名（同 v0.7.0→v0.7.1 同类 bug）, engagement 一直全 None。v0.8.0 README 文档里"xhs 全文在 raw['content']"的话也是错的（OpenCLI 搜索不返正文）。修：`likes:str→int` via `_parse_likes()`, 删 comment_count/collect_count map, 测试 fixture 改用真 OpenCLI shape。README "如何取全文" 表加 twitter 行(长 thread 触发 validator), 删 xhs 行(无全文)。E2E 实测 likes=83/102/45 (was None)。PR #19
- `v0.19.0-alpha` (2026-09-03): **失败契约补洞 + 抖音作者目录 + 扩展自重载** —— (a) `cli.py::_entrypoint` 此前把任何 ClickException 渲染成只有 `error` 没有 `errors` 的信封, agent 读到空列表, 看起来像「跑完了什么都没找到」; 现在 CLI/MCP 每条失败路径都填 `errors`, 崩溃 traceback 改走 stderr, MCP 异常兜底返回真信封而不是 outputSchema 不认的 `{"error": ...}` (issue #45, PR #47)。抖音 fresh-cookies 抖动是实测的: 冷启动 1/10、被限流后 4/10, 1 秒与 5 秒间隔失败率一样 —— **加尝试次数有用、加退避没用**, 定 4 次共享一个 timeout 预算。(b) `omnireach author` + `omnireach_author`: 关键词搜索匹配的是文案, 按点赞排「彭十六」排出来的全是陌生人; 走登录态页面上下文里的 `aweme/v1/web/aweme/post/` (无需 a_bogus/X-Bogus 签名), engagement 是精确值 (issue #46, PR #48)。四个只有真数据才暴露的坑记在 `docs/verification/douyin-author.md`。(c) `omnireach bridge reload` 让扩展自己重载, 1.8 秒, 终结了改扩展必须人工点 `chrome://extensions` 的循环 (PR #51, 验证记录 `docs/verification/bridge-self-reload.md`)。(d) CLAUDE.md 架构边界与版本历史对齐已 ship 的现实, 回填 v0.12→v0.18 (PR #50)。485 tests。扩展 0.4.0, `NATIVE_EXTENSION_MIN_VERSION` 故意不抬 —— 没重载扩展的用户其余命令照常。
- `v0.18.0-alpha` (2026-07-22): **有界抖音下载** — `omnireach media download <douyin-url>` + `omnireach_download_media`, SHA-256 寻址产物、字节数校验、哈希核对后的缓存复用; 匿名验证失败返 `category=blocked` + cookie 恢复提示 + 非零退出码。PR #44。验证记录 `docs/verification/douyin-download.md`。
- `v0.17.0-alpha` (2026-07-22): **media parse 基础** — `media inspect` / `media parse` + `omnireach_parse_media` + `MediaEnvelope` 契约; YouTube 走 yt-dlp, B站默认走匿名官方 read API (需登录的字幕才走显式 `--cookies-from-browser`), 直接媒体走 ffprobe; 签名字幕 URL 与浏览器凭据不入 envelope/manifest。PR #43。**注意: 这一版起「不塞 parse/download 子命令」那条老边界已被推翻, 见上方架构边界节。**
- `v0.16.1-alpha` (2026-07-16): **hotfix 并发多源** — dispatcher 并发跑源, 而每个 native adapter 各自去绑 `127.0.0.1:19826`, 单源过、多源只有第一个能起, 其余 `Address already in use`。改为串行化 native job 并让排队中的 job 可取消。378 tests + 12 JS。PR #38
- `v0.16.0-alpha` (2026-07-16): **六个浏览器源全迁原生桥 + agy grounded search** — google/reddit/twitter/xiaohongshu/tiktok/douyin 全部 native-first (扩展 0.2.8 加命令/版本协商、冷启动安全的 offscreen 初始化、确定性清理、去掉 windows 权限), OpenCLI 降为自动兼容回退; TikTok 改抓真实渲染卡片而非不稳定的私有端点; 新增实验性 `agy` 源 (复用已认证的专属会话 + 其服务端 grounded WebSearch 引用, `omnireach agy configure <conversation-id>`, 只能 `--on agy` 显式调)。377 tests + 12 JS。PR #37
- `v0.15.0-alpha` (2026-07-15): **agent 面失败契约硬化** — fetch 拒收短验证页/登录墙占位符 (真实 Reddit `Please wait for verification` 记为 `captcha_suspected` 并给 opencli 登录态回退); `--sources` 成为 `--on` 别名以对齐 MCP 参数名; heavy 源冷启动默认 60 秒, 显式 `--timeout` 改为覆盖所有选中源 (此前被静默忽略); CLI/MCP 加 `--profile` / `profile` 选 OpenCLI Browser Bridge profile 且不污染父进程环境; doctor 真跑 `opencli doctor` 探针并检测多 profile 冲突。**CLI usage error 在带 `--json` 时输出 JSON 错误信封也是这一版加的 —— 其形状缺 `errors` 字段, 由 issue #45 修正。**373 tests。PR #36
- `v0.14.0-alpha` (2026-07-10): **自带原生 Chrome bridge** — 不再需要 OpenCLI 可执行文件: 自带只读 MV3 扩展 + 无新依赖的 Python localhost bridge (bearer 鉴权、仅回环、短生命周期), `omnireach bridge install|path|status --json`; `douyin.search` 迁到 native-first, OpenCLI 作兼容回退; `OMNIREACH_BROWSER_TRANSPORT=auto|native|opencli` 用于确定性诊断。扩展只接受 `system.ping` 和 `douyin.search`, 不要 cookie/debugger/`<all_urls>` 权限。PR #35
- `v0.13.1-alpha` (2026-07-10): **OpenCLI 运行时错误如实上报** — 此前所有子进程/契约失败都塌缩成 `AdapterUnavailable`, TTY 只显示「1 个源未配置」, 一次真实抖音搜索因此被误报成未配置。改为: 缺 binary 才是 `unavailable`, 非零退出/坏 JSON/坏结构都是带 stderr 详情的 `failed`。PR #34
- `v0.13.0-alpha` (2026-07-10): **google + twitter 进普通搜索** — 装了 OpenCLI 时 `omnireach search` 自动带上这两个源, 走后台 ephemeral tab 复用登录态并用后即关; `--mode quick` 仍然免浏览器, 显式 `--on` 仍然精确。选这条路是因为直连 Google 拿到的是 JS 挑战页, 而 Custom Search JSON API 已对新客户关闭。PR #33
- `v0.12.0-alpha` (2026-07-10): **MCP 快路径** — `omnireach_search` / `omnireach_fetch` 两个模型可调工具 + 无新依赖的 `omnireach mcp` stdio server + Claude plugin 注册; 抽出共享 search/fetch service 让 CLI 与 MCP 共用同一份契约; 修掉「文章里提到 Cloudflare 就被误判为验证页」。实测读同一份 RFC 9110 五次: 冷启动中位数 1383.86ms vs Playwright+headless Chrome 3749.26ms (2.7×), 双方都热时 1311.46ms vs 1687.94ms。PR #29~#32
- `v0.11.0-alpha` (2026-06-22): **对外定位重写 (Senses/Eyes) + AI-native 安装** — 把面向陌生人/agent 的第一屏从"补中转站 WebSearch"(冰山一角)重写成 **"give your agent the senses of a logged-in human across the whole internet"**(冰山主体: search + read 15+ 登录墙垂直源)。README (english-first) + 新 `README.zh.md` 镜像 + `plugin.json` + GitHub repo description + SKILL.md frontmatter description 全部换 Senses/Eyes 框架; 三支柱 (reach the unreachable / one uniform contract / works even when WebSearch doesn't) 占第一屏, 两层 gate 技术解释 + 命名/架构下沉到 `<details>` 折叠区。**AI-native install**: 新 `install.sh` (幂等/非交互/自包含 — 确保 uv → `uv tool install --force` → 把 canonical SKILL.md 落进 `~/.claude/skills/omnireach/`), 人类只说一句话、agent 跑一条 `curl … | sh`; `scripts/verify-install.sh` 静态校验 (非交互/幂等 marker)。SKILL.md 加 step-0 自愈段, 修掉旧的 `pipx install omnireach` 死命令 (从不在 PyPI)。Demo GIF (已于 2026-08-27 迁至 https://raw.githubusercontent.com/Daily-AC/assets/main/omnireach-images/demo.gif) 用 hyperframes 合成 (暗色终端风 + 小红书红点缀, ask-agent→install→search 小红书 flow)。零 Python 行为改动, 278 tests 不变。决策依据见 `docs/design/2026-06-22-repositioning-and-ai-native-install-design.md`。PR #27
- `v0.10.1-alpha` (2026-05-27): **OpenCLI wechat fetch + CAPTCHA detection + host-aware fetch routing** — `omnireach fetch <mp.weixin.qq.com URL>` 现在走 OpenCLI 登录态 Chrome (`opencli weixin download --stdout`) 拿正文 markdown, 替代被验证码拦住的 crwl/jina (v0.10.0 silent-fail bug 真根因)。Click `--backend` choices 扩 `opencli`, default `auto` 时 wechat host 强走 OpenCLI, explicit `--backend X` 永远赢 (CAPTCHA 启发式兜底)。`_looks_like_captcha()` 给所有 backend 加 verification-page 关键词检测 (环境异常 / Cloudflare / Just a moment 等 7 keyword), `errors[]` 加 `captcha_suspected` entry, markdown 字段保留 (graceful degrade, Agent 自己判断)。`omnireach doctor` 加 `wechat_backends` 段, 检测 opencli + `--stdout` flag 是否存在。OpenCLI fork (Daily-AC/OpenCLI) 这边给 `weixin/download` 加 `--stdout` flag (mirror 现有 `web/read` 同款模式, 复用 `ArticleDownloadOptions.stdout` 共享 helper), 同步给 jackwener 提上游 PR #1770。E2E 验: 早上 v0.10.0 被验证码拦住的 mp.weixin.qq.com 文章, v0.10.1 干净拿到 25618 字符真 markdown (backend=opencli, errors=[])。278 tests (256 → 278, +22 host routing / 3-branch parser / CAPTCHA heuristic / wechat_backends doctor). PR #25, fork commit fe28823, upstream PR jackwener/OpenCLI#1770。
- `v0.10.0-alpha` (2026-05-27): **`omnireach fetch <url>` subcommand + `OMNIREACH_FORCE_JSON` env override + Skill manifest Agent contract** — 第一个落地 monorepo sibling-binary 方向的功能, 但作为 subcommand 而非独立 binary (用户偏好"omnireach fetch xxx" 收敛形态)。Dual-backend: crwl (Crawl4AI 本地) 优先, jina (r.jina.ai SaaS) fallback —— 跟 wechat/bilibili 一样的 priority 模式。`--backend auto|crwl|jina` 显式选择。`_should_emit_json()` v0.10 加 `OMNIREACH_FORCE_JSON` env var 兜底 (Antigravity 等真 PTY 子进程场景 isatty=True 让 v0.9.2 自动检测失效, 这是结构性修复)。SKILL.md 加 Agent 调用约定段, 明确"always pass --json 或 set OMNIREACH_FORCE_JSON=1"作为契约。256 tests (243→256, +13 fetch + force-json env)。E2E: `omnireach fetch <hn-url> --json` 实测 crwl 真返 markdown; `--backend jina` 也通 r.jina.ai。PR #24
- `v0.9.3-alpha` (2026-05-27): **monorepo 方向 + doctor 加 fetch backend 段** — 2026-05-27 session 拍板**不开 sister repo**, 改用 monorepo + sibling binary 模型 (类 cargo/rustc/rustfmt, 不类 git+git-lfs)。CLAUDE.md / README 全文把"未来 sister repo"措辞换成"本 repo 未来 sibling binary"。doctor 新加 `fetch_backends` 段, 当前唯一 backend 是 `crwl` (Crawl4AI) — 检测 PATH 在不在, 不在则给 `pip install -U crawl4ai && crawl4ai-setup` install hint。JSON shape 新增 `fetch_backends: [{tool, ok, detail, fix_hint}]`。**search binary 是否改名** (e.g. omnisearch) ~~parked~~ — 2026-05-27 (v0.10 ship 后) **拍板不改**: `omnireach search` + `omnireach fetch` 当 subcommand 用, umbrella 名 `omnireach` 反而契合。243 tests。PR #23
- `v0.9.2-alpha` (2026-05-27): **Agent-first CLI UX — auto JSON when stdout 非 TTY** — Antigravity session 截图发现另一个 Claude 在 omnireach 无 `--json` 时 cli 出 rich Table, URL 在表格 wrap 后难抠, 它选择重跑 `--json` 而不是从 context 拷; 但根因是 omnireach 默认按"人坐在 terminal"渲染。修: `cli.py` 加 `_should_emit_json(flag)` helper — `flag or not sys.stdout.isatty()`。`search` / `doctor` / `sources` 三处都走它; `doctor` / `sources` 新加 `--json` flag (此前不存在)。`setup` **不**做 isatty 检测因 Click 的 prompt/confirm 在 EOF stdin 上已会自然 Abort, 不真死锁, 且 CliRunner 测试也走 BytesIO (isatty=False) 加严格检测会假 trip。240 tests。PR #22
- `v0.9.1-alpha` (2026-05-27): **Exa `contents.text` hotfix** — 自 v0.5 起 Exa 调用一直没传 `contents` 参数, 导致 `--on exa/wechat/bilibili` 的 `result.content` 永远是 ""；只有 v0.9 用 EXA_API_KEY 增强路径才 E2E 暴露这个尾巴。补 `"contents": {"text": {"maxCharacters": 2000}}` 三处 (exa/wechat/bilibili adapter)。maxCharacters=2000 是 4× SearchResult snippet 上限, 单结果 raw 控在 ~2KB 避免 envelope 爆 (不限的话 Exa 单条返 10–60KB)。E2E 验: content_len=501, raw_text_len≈2000。PR #21
- `v0.9.0-alpha` (2026-05-27): **wechat/bilibili 解锁免费路径** — 两源从 💎 booster 升 ✅ ready, 默认走 Sogou 微信搜索 (httpx + lxml 直抓) 与 B站官方 search API (httpx + json, 仅需 `Referer: search.bilibili.com`)。`EXA_API_KEY` 不再必需, 设置后作为 enhanced backend 提供语义增强 (优先级 Exa > 免费 fallback)。新增 `SourceSpec.enhanced_with: str | None` 字段表达"可选环境变量启用增强"语义。`default_in_auto` 翻为 false (Sogou ~3s 延迟拖累 auto fanout, 走 query hint 或 --on)。新依赖: `lxml`, `cssselect`。新文件: `_wechat_sogou.py`, `_bilibili_api.py`, 两个真实 fixture。Scrapling 仍可选作 Sogou 的 stealth 增强 (import 检测式, 不强依赖)。源调研由 omnireach 自己搜 Twitter+GitHub 完成 (Agent-Reach wechat.py 也是 Exa, wewe-rss/wechat-article-exporter 是订阅/导出不是搜索, 真路径只能是 Scrapling/Camoufox/Sogou)。25x tests。PR #20

## v0.7 后续 (开着的)

- **上游切回 (2026-06-23 更新, 只对了一半)**: PR #1759 (douyin search) **已 merged** (2026-05-31), 作者 review 时做了质量改进 (`extractDouyinVideoId` 抽取 / `isSearchCardMetadataText` 过滤噪音文本 / `isProjectedRowUsable` 行过滤), 但 **字段契约不变** (`rank/desc/author/url/plays/likes/comments/shares`) —— omnireach `--on douyin` 真 E2E 验过零回归 (返 10 条, likes 真实, 其余 0→None)。**但 PR #1770 (weixin `--stdout`) 仍 OPEN**, upstream 没这个 flag, 而 omnireach wechat fetch (v0.10.1) 依赖它 —— **所以 sources.yml 5 处 `github:Daily-AC/OpenCLI` 暂不能切回 `@jackwener/opencli`** (会丢 --stdout)。等 #1770 也 merged 才能完全切回。当前 fork `main` 已 merge upstream (2026-06-23), 状态 = upstream 全部 + 唯一 delta (weixin `--stdout`); douyin 已 = upstream 版。
- **twitter delete i18n 修复** (2026-06-23): fork `delete.js` 在中文 X UI 上挂 (`aria-label === 'More'` 精确匹配 miss 了 zh 的「更多」), 加上详情页 article 晚 hydrate。修法: caret 用 `[data-testid="caret"]` + 多语言 aria-label 兜底, `findTargetArticle()` 轮询 ~5s, Delete 菜单项加「删除」。fork 分支 `fix/twitter-delete-i18n` 已 push, upstream issue [jackwener/OpenCLI#2001](https://github.com/jackwener/OpenCLI/issues/2001)。
- TikHub.io 方向已撤 (用户在 v0.7 session 喊停, 改 OpenCLI 逆向路线)

## v0.8 候选

- ~~4 个长文本源 content 字段截断到 ~500 字 snippet~~ ✅ done in v0.8.0-alpha
- ~~Scrapling 给 wechat/bilibili 做"无 EXA Key 也能跑"的免费降级路径~~ ✅ done in v0.9.0-alpha (实际未用 Scrapling, 用 httpx+lxml; Scrapling 仍可选作 Sogou stealth 增强)
- 跨平台 setup wizard (gh on Linux/Windows)
- usage tracking + monthly budget cap for boosters
- xhs-cli 替换 OpenCLI 小红书路径 (agent-reach references 推荐 xhs)
- `omnireach search` query-aware mode selection (URL → rss only 等)

## v1.x wishlist

- `omnireach diagnose --autopr` (用户 agent 自动 fix upstream bug 后自动 PR 回 repo)
- e2e CI matrix 装真实 yt-dlp/gh/opencli docker images
- 公开发布到 Claude Marketplace
- **fetch 当前架构 (2026-07-10)**: 默认普通网页走 repo 自带的轻量 HTTP + HTML-to-Markdown，遇到验证页或提取失败回退 Jina；`mp.weixin.qq.com` 走 OpenCLI 登录态后台临时 tab；`crwl` 只保留显式 `--backend crwl` opt-in。OpenCLI adapter 全部显式传 `--window background --site-session ephemeral --keep-tab false`，并在 dispatcher 取消时回收子进程。基础依赖已移除 `lxml/cssselect`。
- **Agent fast path (2026-07-10)**: 只读联网任务先用 MCP `omnireach_search` / `omnireach_fetch`，MCP 不可用才回退 CLI；Playwright 只保留给点击、表单、上传下载、截图、视觉验证和未支持的交互流程。`.mcp.json` 在 plugin root 自动注册 `omnireach mcp`。
- (Apache-2.0 License 切换问题不再适用 — monorepo 模型下整个仓库统一 MIT)

## 外部 issue 历史

- #12 (求抖音源, menoking 提, 2026-05-26): v0.7.2 用 OpenCLI fork 路线解决, 已 close。不走 TikHub.io 付费 API (用户喊停)。OpenCLI 上游 PR #1759 已 merged (2026-05-31, 见上方「上游切回」节)。

## 关键文档 (绝对路径)

- 设计 spec: `docs/design/2026-05-25-omnireach-design.md` (甲方决策全锁在 §3)
- v0.6 retrospective: `docs/retrospectives/2026-05-26-v0.3-v0.5-lessons.md`
- v0.8 spec: `docs/design/2026-05-27-omnireach-v0.8-design.md`
- v0.9 spec: `docs/design/2026-05-27-omnireach-v0.9-design.md`
- 2026-05-26 session handoff: `docs/handoff/2026-05-26-session-handoff.md`
- 真实 E2E 验证记录: `docs/verification/`（抖音下载 / media v0.17 / 抖音作者目录）—— 这里记的是
  只有真跑才会暴露的上游行为，改相关代码前先看，别重新踩
- 发版记录: `docs/releases/`（v0.12 起每版一份，2026-09-03 回填了 v0.15/v0.16/v0.16.1）
- README: `README.md`

> 2026-08-27: `docs/superpowers/` 拆分完毕 —— 13 个 spec 迁到 `docs/design/`（设计决策，长期有效），
> 13 个 plan 删除（执行计划，做完即失效）。superpowers 框架本身早已卸载，目录名不再保留。

## 获客/分发状态 (2026-07-07 session)

- **PyPI 已上线** (0.11.0a0): 发布走 `uv build && uv publish --token "$PYPI_TOKEN"` (token 在 `~/.secrets/vault.env`, 记得 source)。**未来每次 release 除 gh release 外还要 uv publish**。sdist 有 exclude 配置保持 ~51KB。待办: 用户把全账号 token 换成 omnireach 项目级。
- **定位已换楔子** (PR #28): 弃 "senses/eyes"(与 Agent-Reach 51k★ 撞车) 改 "login-walled Chinese internet + 零配置微信搜索 + 统一 JSON 契约"。README 有 vs Agent-Reach 对比表 (事实依据: 对方 2026-06 PR #347 删除微信/抖音/微博, 无统一 schema 是其设计哲学)。改第一屏前先重验对比表事实是否过期。
- **demo**: docs/assets/demo-wechat.gif 为真实 VHS 录制 (tape 同目录, 可复现; 需 brew vhs, 渲染时清空 booster env 走免费路径)。
- **GitHub topics ×12 已挂; repo description 已换楔子。**
- **awesome 列表 PR**: ComposioHQ/awesome-claude-skills#1239, 1c7/chinese-independent-developer#1062, BehiSecc/awesome-claude-skills#429 (2026-07-07 提交, 定期看是否被 merge)。hesreallyhim/awesome-claude-code 规则要求先有用户量, awesome-cli-apps 要 20★+3 个月 — 都等有量再投。
- **首发帖**: 文案在 docs/launch-drafts/ (gitignored), 计划 linux.do → V2EX → 即刻/Twitter → Show HN 同周脉冲, 进度见同目录 progress.md。
- **spam PR 处理先例**: PR #26 (kriptoburak/TweetClaw) 为 5682 连发推广战役一部分, 已关闭并留评。同类供应商自荐付费源集成一律拒。

## Release 流程 (v0.5.1 起强制)

- 推 tag 后**必须** `gh release create vX.Y.Z-alpha --title "..." --notes "..."` 否则 `omnireach check-update` 走 `/releases/latest` 会 404
- 如果同时创建多个 release, GitHub 把最后创建的标为 Latest, 不是 tag 顺序; 用 `gh release edit vLATEST --latest` 修正
- **不要给 alpha release 加 `--prerelease`**: GitHub 的 `/releases/latest` 端点按定义跳过 prerelease, 而 `check-update` 正是读这个端点 —— v0.19 用 `--prerelease` 发出去后, 它仍然把 v0.18 当最新, 老用户永远收不到升级提示。修法 `gh release edit vX.Y.Z-alpha --prerelease=false --latest`。本仓库的历史是混的 (v0.16/v0.16.1 是 prerelease, v0.17/v0.18 不是), 别照抄相邻的那一版。
- check-update 实现走 GitHub Releases API, 见 `omnireach/commands/check_update.py`
- **版本号有四处源, bump 时四处都要改**: `omnireach/__init__.py __version__` (CLI `--version` 读这里) + `pyproject.toml [project] version` (build/wheel 元数据, static 不是 dynamic) + `.claude-plugin/plugin.json version` + `uv.lock` (改完跑 `uv lock` 同步)。`tests/test_version_metadata.py` 会钉死前三处一致 —— v0.19 bump 时就是它抓到 plugin.json 漏改。v0.11.0 踩过: 只改了 `__init__` 导致 build 元数据落在旧版; `omnireach --version` 与 wheel 版本不一致。

## 工作偏好 (来自用户跨项目 feedback memory, 这里只记跟 omnireach 有关的部分)

- **甲方模式**: 中长项目走「甲方模式」, ≤4 个真甲方决策批量问, 技术/流程细节默默执行。PR "一气呵成"已授权, 不要每步停下问。
- **Agent-first CLI UX**: omnireach 的目标用户是 Agent (中转站 + cliproxy Agent 用户), 但默认 cli 行为容易落入"人坐在 terminal"假设。每加一个 cli 子命令 / 新输出, 主动问"这个东西塞到 Agent stdout pipe 里是不是噩梦"。具体规则: (a) 凡是有 rich.Table 渲染的命令都要支持 `--json` 显式 flag + `not sys.stdout.isatty()` 自动 JSON; (b) 有 click.prompt/confirm 的命令至少在错误信息里点明"这是 interactive, Agent 别调"; (c) 测试用 monkeypatch `_should_emit_json` 强行走 TTY 分支因为 CliRunner stdout 是 BytesIO (isatty=False)。Why: v0.9.2 session 里 user 截图给一个 Antigravity 的另一个 Claude 在 omnireach 无 --json 时浪费一次 tool call 重跑, 根因是 omnireach default UX 错。
- **真实 E2E 才能 ship**: 新加 adapter 必须真跑过 `omnireach search --on <src> --json "<query>"` 看上游真实返回字段, mock test 通过不算完成。v0.7.0 → v0.7.1 hotfix 就是因为字段名是猜的没真跑过; v0.8.0 → v0.8.1 hotfix 又踩同坑（contract 层 validator spec 写「不需要 E2E」, 但 E2E 时发现 v0.5.2 起的 xhs adapter pre-existing 字段映射 bug 一直没人测出来）。**规则升级**: 即使本次改动只动 contract / normalizer 这类"远离上游"的层, 也要 E2E 一遍受影响的源（包括"应该没事"的源）来验证 mock fixture 跟现实没漂移。spec 写「不需要 E2E」时主动挑战自己。
- **外部 issue 不让 reporter 做技术决策**: 自己调研 + 自己拍方向 + 简短礼貌回复 + 加 milestone。
- **新源 adapter 流程**: 通常按 brainstorming → writing-plans → subagent-driven-development 推进。每个 milestone 走 push → PR → squash merge → 删 feat 分支 → tag → gh release create 流程。

## How to apply (未来在 omnireach 目录启动 CC 时)

用户喊「继续干 omnireach」时，先看 GitHub 上开着的 issue（那是当前真实待办，比本文里的「v0.8 候选」新），
再按上面「架构边界」判断该功能属于哪一层。涉及 OpenCLI 相关动作时记得当前是 fork (Daily-AC/OpenCLI)
不是 upstream (@jackwener/opencli)；上游 PR #1759 (douyin search) 已合并，但 #1770 (weixin `--stdout`)
仍 OPEN，所以还不能切回上游。

**改 `omnireach/chrome_extension/` 下的代码要注意**：`omnireach bridge install` 只是把文件拷到
`~/.omnireach/chrome-extension`，运行中的 Chrome 不会加载新代码，MV3 service worker 空闲重启也不会。
判据是 `omnireach bridge status --json` 的 `reload_required` / `connected_version`。
**v0.19 起用 `omnireach bridge reload` 让扩展自己重载**（走 `chrome.runtime.reload()`，1.8 秒，
service worker 与 offscreen document 都会自动回来 —— 实测记录见 `docs/verification/bridge-self-reload.md`）；
在此之前只能人工去 `chrome://extensions` 点「重新加载」，因为 Chrome 136+ 不向 CDP 暴露扩展 target。
**但纯逻辑仍然先在 `douyin.js` 这类 node 可测的层里用 `node --test tests/js/native-extension.test.mjs`
钉死，再上真浏览器 —— 重载变便宜了不等于真浏览器适合当调试循环。**
