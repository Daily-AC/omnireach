# CLAUDE.md — omnireach 项目协作上下文

This file is loaded automatically when Claude Code starts in this repo. It carries omnireach project knowledge that previously lived in user-global memory; centralizing it here lets the context follow the repo across machines and sessions.

## 项目是什么

**omnireach 是项目名, 同 repo 内会出多个 sibling binary**, 不是单一工具。完整"触达全网"语义由三层职责实现, 三层都会作为同 repo 的 sibling binary 存在（**不开 sister repo**, 拍板于 2026-05-27 session）:

- **`omnireach`** (当前 binary): search 层 — 全网定位 metadata + URL, **不取内容**
- **fetch binary** (暂未实现, 未来加在本 repo): fetch 层 — 给定 URL 取全文 markdown
- **parse binary** (暂未实现, 未来加在本 repo): parse 层 — 视频/音频内容解析

类比 `cargo` (一个 repo 下 `cargo` / `rustc` / `rustfmt` 多个 sibling binary, 共享一个项目愿景) 而不是 `git` + `git-lfs` (后者是 standalone separate repo)。**Why monorepo 而非 multirepo**: 2026-05-27 session 调研 Crawl4AI 时验证 —— 收纳 `crwl` 作为 fetch 工具不影响 search 行为, 只补齐 search 结果, 完全没有 sister repo 的耦合协调成本。一个 release 频道 + 一个 issue tracker + 一份 README 就够。

**search binary 名是否改名**: 当前 `omnireach` 这个 binary 名既是项目名又是 search binary, 长期语义上不准 (reach 是触达, search 只是触达的第一步)。是否改 binary 名 (e.g. `omnisearch`) 至今未决, 2026-05-27 session 显式 parked, 等专门讨论。

本 binary 只做 search。用户问"加 fetch/parse 能力到 omnireach 里"时**应拒绝** (但拒绝的方向不是"去开 sister repo", 而是"等本 repo 加 sibling binary"); 见下方"架构边界"。

## 目标用户与痛点

omnireach 是给中转站 (cliproxy / anyrouter / 各类 OpenAI 兼容代理) 的 Agent 用户的工具, 因为他们用不了 Anthropic 原生 WebSearch。CLI + Claude Code Skill 双形态。

**Why**: 中转站丢掉的服务端工具里 WebSearch 损失最重 —— Twitter / Reddit / 小红书 / B站 / 抖音 / 微信 全够不着。用户痛点是这个, 不是 web 搜索本身。

- 位置: `~/Projects/omnireach`
- GitHub: https://github.com/Daily-AC/omnireach (Public, MIT, 归属 Daily-AC)

## 架构核心 — Umbrella + 适配器壳（v0.5 修订）

- 上游 binary 直调: `yt-dlp` (youtube) / `gh` (github) / `rdt-cli` (reddit) / Python `feedparser` (rss)
- OpenCLI bridge (Node + 登录态 Chrome) → twitter / xiaohongshu / tiktok / douyin
- HN 直接调 Algolia Search API（无上游）
- Boosters (Tavily / Brave / Perplexity / Exa) → httpx 调付费 API，env var 检测式接入
- Agent-Reach **完全可选**（v0.5 起）: 仅作 `setup --batch` 一键引导 installer，runtime 不依赖

omnireach 自己只做: 路由 (Router) + 并发分发 (Dispatcher) + 归一 (Normalizer/Scorer) + 引导 (Wizard) + 标准化 JSON 契约 (SearchResult/SearchEnvelope, pydantic v2)。

## Tier 系统 (5 tier, sources.yml 中声明)

- ✅ `ready`: 零配置或一条 `pip install` 可用 (HN/youtube/github/rss)
- 🟡 `one_step`: 一次 OAuth/Key 配置 (reddit 需 `rdt login`)
- 🔴 `heavy`: 装 Chrome 扩展 + 浏览器登录态 (twitter / xiaohongshu / tiktok / douyin)
- 💎 `booster`: 付费 API Key (Tavily/Brave/Perplexity/Exa)，env var 检测，结果元数据 `cost="paid"`
- 🚧 `wip`: 待重写源，sources 列表显示但不参与 auto fanout (v0.7 起暂无 wip 源)

## 架构边界 — 三层架构 (v0.7 session 拍板, 必须遵守)

对照 Claude Code 的 WebSearch + WebFetch 拆分，omnireach 是三层架构里的最上层:

```
omnireach    → 多源 WebSearch (返 metadata + URL, 不取内容)        ← 本 repo
omnifetch    → 多源 WebFetch (给定 URL 取全文 markdown)              ← 未来 sister repo
omniparse    → 视频/音频专项 fetch (字幕/STT/逐帧)                    ← 未来 sister repo
```

**Why**: search vs parse 是不同职责。把解析塞进 search 会让边界变模糊、token 爆炸、违反"do one thing well"。Claude Code 自己 WebSearch + WebFetch 就是这么拆的; OpenAI Codex 走相反路线 (单 `web_search` 黑箱), 我们不抄。

**永远不做的事** (违反三层架构 → 立刻拒绝):
- 不要在 omnireach 里塞 `download` / `parse` / `fetch-content` 子命令
- 不要在 omnireach adapter 里跑 LLM call 做 summary (会引入 LLM 依赖, 让工具变"小 Agent")
- 视频源 (youtube / bilibili / tiktok / douyin) 只返 metadata, **不抓视频直链 mp4 CDN**
- 长文本源 (wechat / xhs / exa / tavily) content 字段应截到 ~500 字 snippet (v0.8 起由 `SearchResult` validator 强制), 全文保留在 `result.raw` 中, Agent 按需取用; 真要 omnifetch 才能拿的是 omnireach 本来就没全文的场景 (HN/GH/Twitter thread 等)
- 用户问"加 X 功能"时, 先判断 X 属于 search / fetch / parse 哪层, 不属于 search 就拒绝**并指向本 repo 未来 sibling binary** (v0.8 之前的措辞是"指向未来 sister repo", 2026-05-27 改成 monorepo 模型 — 见上方"项目是什么"节)

**~~当前违规~~已修** (v0.8 修复): 4 个长文本源 (wechat/xiaohongshu/exa/tavily) 在 `SearchResult.content` 上的全文塞入由 contract 层 `field_validator` 截到 500 字 + "…"; 全文保留在 `result.raw` 中。见 `docs/superpowers/specs/2026-05-27-omnireach-v0.8-design.md`。

**为什么 v0.8 不抄 Claude Code 的 LLM-summarized snippet**: Claude Code 用 sub-LLM (Haiku) 压缩 snippet 是因为 user-facing 直接看; omnireach 用户 = Agent (本身就是 LLM), 拿到截断 raw 自己能消化, 不需要 omnireach 替它压缩。抄了反而让 omnireach 从"纯多源汇聚 + 零 LLM 依赖"变成"小 Agent + LLM key 必需", 边界模糊化。

**fetch / parse binary 启动时机**: 等用户提"我要全文" / "我要视频内容"的真 issue 再在本 repo 加新 binary (YAGNI), **不开 sister repo** (2026-05-27 拍板)。当前临时方案: README「如何取全文」段写了 `omnireach + crwl` 手动 pipeline; 等真要做 fetch binary 时, 它可能就是个 crwl 的 thin orchestrator。

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
- `v0.9.3-alpha` (2026-05-27): **monorepo 方向 + doctor 加 fetch backend 段** — 2026-05-27 session 拍板**不开 sister repo**, 改用 monorepo + sibling binary 模型 (类 cargo/rustc/rustfmt, 不类 git+git-lfs)。CLAUDE.md / README 全文把"未来 sister repo"措辞换成"本 repo 未来 sibling binary"。doctor 新加 `fetch_backends` 段, 当前唯一 backend 是 `crwl` (Crawl4AI) — 检测 PATH 在不在, 不在则给 `pip install -U crawl4ai && crawl4ai-setup` install hint。JSON shape 新增 `fetch_backends: [{tool, ok, detail, fix_hint}]`。**search binary 是否改名 (e.g. omnisearch) 仍 parked**, 等专门讨论。243 tests。PR #23
- `v0.9.2-alpha` (2026-05-27): **Agent-first CLI UX — auto JSON when stdout 非 TTY** — Antigravity session 截图发现另一个 Claude 在 omnireach 无 `--json` 时 cli 出 rich Table, URL 在表格 wrap 后难抠, 它选择重跑 `--json` 而不是从 context 拷; 但根因是 omnireach 默认按"人坐在 terminal"渲染。修: `cli.py` 加 `_should_emit_json(flag)` helper — `flag or not sys.stdout.isatty()`。`search` / `doctor` / `sources` 三处都走它; `doctor` / `sources` 新加 `--json` flag (此前不存在)。`setup` **不**做 isatty 检测因 Click 的 prompt/confirm 在 EOF stdin 上已会自然 Abort, 不真死锁, 且 CliRunner 测试也走 BytesIO (isatty=False) 加严格检测会假 trip。240 tests。PR #22
- `v0.9.1-alpha` (2026-05-27): **Exa `contents.text` hotfix** — 自 v0.5 起 Exa 调用一直没传 `contents` 参数, 导致 `--on exa/wechat/bilibili` 的 `result.content` 永远是 ""；只有 v0.9 用 EXA_API_KEY 增强路径才 E2E 暴露这个尾巴。补 `"contents": {"text": {"maxCharacters": 2000}}` 三处 (exa/wechat/bilibili adapter)。maxCharacters=2000 是 4× SearchResult snippet 上限, 单结果 raw 控在 ~2KB 避免 envelope 爆 (不限的话 Exa 单条返 10–60KB)。E2E 验: content_len=501, raw_text_len≈2000。PR #21
- `v0.9.0-alpha` (2026-05-27): **wechat/bilibili 解锁免费路径** — 两源从 💎 booster 升 ✅ ready, 默认走 Sogou 微信搜索 (httpx + lxml 直抓) 与 B站官方 search API (httpx + json, 仅需 `Referer: search.bilibili.com`)。`EXA_API_KEY` 不再必需, 设置后作为 enhanced backend 提供语义增强 (优先级 Exa > 免费 fallback)。新增 `SourceSpec.enhanced_with: str | None` 字段表达"可选环境变量启用增强"语义。`default_in_auto` 翻为 false (Sogou ~3s 延迟拖累 auto fanout, 走 query hint 或 --on)。新依赖: `lxml`, `cssselect`。新文件: `_wechat_sogou.py`, `_bilibili_api.py`, 两个真实 fixture。Scrapling 仍可选作 Sogou 的 stealth 增强 (import 检测式, 不强依赖)。源调研由 omnireach 自己搜 Twitter+GitHub 完成 (Agent-Reach wechat.py 也是 Exa, wewe-rss/wechat-article-exporter 是订阅/导出不是搜索, 真路径只能是 Scrapling/Camoufox/Sogou)。25x tests。PR #20

## v0.7 后续 (开着的)

- **上游切回**: jackwener 一旦 merge PR #1759 + OpenCLI 发新版, 把 sources.yml 里 4 处 `github:Daily-AC/OpenCLI` 改回 `@jackwener/opencli` (douyin adapter 代码本身不动, 字段 shape 一致)。出 v0.7.3-alpha
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
- e2e CI matrix 装真实 yt-dlp/gh/rdt-cli/opencli docker images
- 公开发布到 Claude Marketplace
- **本 repo 加 fetch binary 时, default backend 候选**: [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) (66K stars, Apache-2.0, Python+Playwright, 输出 Markdown, 内置反爬绕过 Cloudflare/Akamai/PerimeterX/DataDome) + [jina-ai/reader](https://github.com/jina-ai/reader) (10K stars, `r.jina.ai/<url>` 极简 SaaS, 免费额度大) 作 SaaS fallback。**注意 Crawl4AI 代码结构有 monolith 倾向** (extraction_strategy.py 120KB / async_crawler_strategy.py 118KB), fetch binary 立项时主动避免这个坑。当前临时方案: README「如何取全文」里写的 `omnireach + crwl` 手动 pipeline + doctor 报 crwl 是否在 PATH (v0.9.3 起)。
- (Apache-2.0 License 切换问题不再适用 — monorepo 模型下整个仓库统一 MIT)

## 外部 issue 历史

- #12 (求抖音源, menoking 提, 2026-05-26): v0.7.2 用 OpenCLI fork 路线解决, 已 close。不走 TikHub.io 付费 API (用户喊停)。OpenCLI 上游 PR #1759 等 review。

## 关键文档 (绝对路径)

- 设计 spec: `docs/superpowers/specs/2026-05-25-omnireach-design.md` (甲方决策全锁在 §3)
- 历史 plans: `docs/superpowers/plans/2026-05-25-omnireach-v0.{1,2,3,4}.md` + `2026-05-26-omnireach-v0.{5,6}.md` + `2026-05-27-omnireach-v0.8.md`
- v0.6 retrospective: `docs/retrospectives/2026-05-26-v0.3-v0.5-lessons.md`
- v0.8 spec: `docs/superpowers/specs/2026-05-27-omnireach-v0.8-design.md`
- v0.9 spec: `docs/superpowers/specs/2026-05-27-omnireach-v0.9-design.md`
- 2026-05-26 session handoff: `docs/handoff/2026-05-26-session-handoff.md`
- README: `README.md`

## Release 流程 (v0.5.1 起强制)

- 推 tag 后**必须** `gh release create vX.Y.Z-alpha --title "..." --notes "..."` 否则 `omnireach check-update` 走 `/releases/latest` 会 404
- 如果同时创建多个 release, GitHub 把最后创建的标为 Latest, 不是 tag 顺序; 用 `gh release edit vLATEST --latest` 修正
- check-update 实现走 GitHub Releases API, 见 `omnireach/commands/check_update.py`

## 工作偏好 (来自用户跨项目 feedback memory, 这里只记跟 omnireach 有关的部分)

- **甲方模式**: 中长项目走「甲方模式」, ≤4 个真甲方决策批量问, 技术/流程细节默默执行。PR "一气呵成"已授权, 不要每步停下问。
- **Agent-first CLI UX**: omnireach 的目标用户是 Agent (中转站 + cliproxy Agent 用户), 但默认 cli 行为容易落入"人坐在 terminal"假设。每加一个 cli 子命令 / 新输出, 主动问"这个东西塞到 Agent stdout pipe 里是不是噩梦"。具体规则: (a) 凡是有 rich.Table 渲染的命令都要支持 `--json` 显式 flag + `not sys.stdout.isatty()` 自动 JSON; (b) 有 click.prompt/confirm 的命令至少在错误信息里点明"这是 interactive, Agent 别调"; (c) 测试用 monkeypatch `_should_emit_json` 强行走 TTY 分支因为 CliRunner stdout 是 BytesIO (isatty=False)。Why: v0.9.2 session 里 user 截图给一个 Antigravity 的另一个 Claude 在 omnireach 无 --json 时浪费一次 tool call 重跑, 根因是 omnireach default UX 错。
- **真实 E2E 才能 ship**: 新加 adapter 必须真跑过 `omnireach search --on <src> --json "<query>"` 看上游真实返回字段, mock test 通过不算完成。v0.7.0 → v0.7.1 hotfix 就是因为字段名是猜的没真跑过; v0.8.0 → v0.8.1 hotfix 又踩同坑（contract 层 validator spec 写「不需要 E2E」, 但 E2E 时发现 v0.5.2 起的 xhs adapter pre-existing 字段映射 bug 一直没人测出来）。**规则升级**: 即使本次改动只动 contract / normalizer 这类"远离上游"的层, 也要 E2E 一遍受影响的源（包括"应该没事"的源）来验证 mock fixture 跟现实没漂移。spec 写「不需要 E2E」时主动挑战自己。
- **外部 issue 不让 reporter 做技术决策**: 自己调研 + 自己拍方向 + 简短礼貌回复 + 加 milestone。
- **新源 adapter 流程**: 通常按 brainstorming → writing-plans → subagent-driven-development 推进。每个 milestone 走 push → PR → squash merge → 删 feat 分支 → tag → gh release create 流程。

## How to apply (未来在 omnireach 目录启动 CC 时)

用户喊「继续干 omnireach」或 「v0.8」时，按上面"v0.8 候选"挑一两件优先级最高的开干，遵守三层架构边界（违反就拒绝并解释）。涉及 OpenCLI 相关动作时记得当前是 fork (Daily-AC/OpenCLI) 不是 upstream (@jackwener/opencli)，上游 PR #1759 状态决定 v0.7.3 是否成立。
