# omnireach Session Handoff — 2026-05-26

> 这份文档是 2026-05-26 一次长 session 的收尾交接,给下一个开发 session(无论是 Claude / Codex / 人) 用。  
> 读完前 3 节就能立刻接着干,不需要回看历史 chat。

## §0 当前状态一句话

omnireach v0.6.3-alpha 已 ship,9 个 release 全在 GitHub,198 tests green。**唯一待办的真甲方事项是 issue #12 (抖音源,已锁 TikHub.io booster 方向,挂 v0.7 milestone),下次 session 直接照本文 §3 起 spec → plan → 实施。**

---

## §1 截止 2026-05-26 21:00 的真实状态

### 版本 / Release

| Tag | 发布日 | 关键变更 |
|---|---|---|
| v0.1.0-alpha | 05-25 | core + 7 ready 源 + Skill manifest |
| v0.2.0-alpha | 05-25 | wizard + reddit + HN→Algolia + --on 警告 |
| v0.3.0-alpha | 05-25 | twitter + xiaohongshu via OpenCLI (heavy) + wizard verify |
| v0.4.0-alpha | 05-25 | 💎 booster (Tavily/Brave/Perplexity) + preferences.toml + trust ranking |
| v0.5.0-alpha | 05-25 | **架构 bug 修复**: adapter 不再误用 agent-reach,改直调上游 binary;web 降级 booster (Exa);wechat/bilibili 标 🚧 wip |
| v0.5.1-alpha | 05-25 | `omnireach check-update` 命令 + README 升级章节 |
| v0.5.2-alpha | 05-25 | opencli adapter contract hotfix (`--json` → `--format json`,list-aware parsing,30s 默认 timeout) |
| v0.6.0-alpha | 05-26 | wechat/bilibili wip→💎 booster (Exa domain-filtered);per-source `timeout_seconds`;dispatcher errors 分类 unavailable/failed;verify-adapter-contracts.sh;README 跨 CLI 行 |
| v0.6.1-alpha | 05-26 | `omnireach init` 不再 `pipx install agent-reach` (死代码清理) |
| v0.6.2-alpha | 05-26 | `.github/ISSUE_TEMPLATE/` × 4 (YAML form) + TTY failed errors 加 issue link footer + 全局 `_entrypoint()` 异常 wrapper |
| v0.6.3-alpha | 05-26 | Windows hardening (4 处 macOS 假设解耦) + `doctor` 顶部 platform info 行 |

### 仓库 health

- GitHub: https://github.com/Daily-AC/omnireach (Public, MIT, Daily-AC 个人账号)
- 11 个 PR 全 squash-merged
- 11 个 GitHub Release 全有 Release object (`/releases/latest` 走得通)
- 198 tests green (`uv run pytest`)
- 1 star, 0 fork (alpha 正常)
- 1 open issue: **#12 求抖音源** (本次 session 唯一外部反馈)

### 仓库 layout (核心模块)

```
omnireach/
├── adapters/             # 每源一个 adapter
│   ├── base.py           # AdapterBase 抽象 + AdapterUnavailable 异常
│   ├── hackernews.py     # HTTP API (Algolia), zero-config
│   ├── youtube.py        # subprocess yt-dlp ytsearch{N}: --dump-json
│   ├── github.py         # subprocess gh search repos/issues --json
│   ├── reddit.py         # subprocess rdt-cli search --json --limit
│   ├── rss.py            # Python feedparser (URL-only query)
│   ├── twitter.py        # subprocess opencli twitter search --format json
│   ├── xiaohongshu.py    # subprocess opencli xiaohongshu search --format json
│   ├── tavily.py         # httpx → api.tavily.com (booster, TAVILY_API_KEY)
│   ├── brave.py          # httpx → api.search.brave.com (booster)
│   ├── perplexity.py     # httpx → api.perplexity.ai (booster, sonar-pro)
│   ├── exa.py            # httpx → api.exa.ai/search (booster, EXA_API_KEY)
│   ├── wechat.py         # 同 exa.py 模板 + includeDomains=mp.weixin.qq.com
│   └── bilibili.py       # 同 exa.py 模板 + includeDomains=bilibili.com
├── commands/             # CLI subcommands (init/setup/sources/doctor/preferences/check_update)
├── contract.py           # SearchResult / SourceError / SearchEnvelope (pydantic v2)
├── dispatcher.py         # async 并发 fanout + per-source timeout + error 分类
├── registry.py           # sources.yml 加载 → SourceSpec dataclass
├── router.py             # query → list[source_id] (含 URL-only rss gate)
├── scorer.py             # rank by 0.4*recency + 0.6*source_trust
├── normalizer.py         # build_envelope helper
├── doctor.py             # 每源 ready/binary/key 检查 → SourceStatus[]
├── preferences.py        # ~/.omnireach/preferences.toml (pydantic v2)
├── secrets_env.py        # ~/.omnireach/secrets.env dotenv loader
├── installer.py          # pipx/npm install helpers (setup wizard 用)
├── wizard.py             # 共用 setup 交互助手
├── cli.py                # click 主入口 + _entrypoint() 异常 wrapper
└── sources.yml           # 13 源 schema (id/tier/adapter/trust/timeout_seconds/...)
```

---

## §2 v0.7 milestone (GitHub 上已创建)

按优先级:

| # | 项 | 来源 | 估时 |
|---|---|---|---|
| 1 | **TikHub.io booster 抖音支持** (issue #12) | 真用户 | 1-2h |
| 2 | usage tracking + monthly budget cap for boosters | v0.5 retro | 3h |
| 3 | dispatcher errors UX 继续打磨 (per-source vs all-failed) | 自评 | 1h |
| 4 | xhs-cli 替换 OpenCLI 小红书路径 | agent-reach 推荐 | 2h |
| 5 | 跨平台 setup wizard (gh on Linux/Windows) | v0.6.3 后续 | 2h |
| 6 | query-aware mode selection (URL → rss only 等) | v0.6 retro | 1h |
| 7 | (备选) OpenCLI douyin hashtag 作为 #1 补充 | 调研 | 1h |

**强烈建议下一个 session 先做 #1 + #2**:#1 给真用户 ship 反馈关闭循环,#2 是付费功能里 user 最容易踩的坑 (一不小心烧钱)。

---

## §3 抖音/TikHub 行动方案 (Issue #12)

**方向已锁,无需再询问 user**。原因看 §5。

### 实现路径 (照搬 v0.4 booster pattern)

文件级 1:1 类比:

```
adapters/tavily.py   →   adapters/tikhub.py     (新增)
tests/adapters/test_tavily.py → tests/adapters/test_tikhub.py
```

具体修改清单:

1. **新增 `omnireach/adapters/tikhub.py`**(150 行内)
   - class `TikHubAdapter(AdapterBase)`, `name = "tikhub"`, `requires = []`
   - `is_ready()`: `return bool(os.environ.get("TIKHUB_API_KEY"))`
   - `search()`: httpx POST 到 TikHub 抖音视频搜索 endpoint
   - **TikHub endpoint 需要先去文档确认**: https://api.tikhub.io/ (Swagger UI),找 `/api/v1/douyin/.../search`
   - **建议在 spec 阶段先 curl 一次 endpoint** 看真实 response shape,别凭脑内想
   - 标 `cost="paid"`,trust 推荐 0.70 (抖音平台数据 vs Tavily 通用 web 0.85)

2. **`omnireach/sources.yml`**: 新增 tikhub 条目

```yaml
- id: tikhub
  tier: booster
  adapter: omnireach.adapters.tikhub.TikHubAdapter
  description: TikHub.io 抖音视频搜索 (付费 API)
  query_hints: [抖音, douyin, tiktok]
  default_in_auto: true
  trust: 0.70
  timeout_seconds: 15
  deps:
    auto: []
    manual:
      - step: "去 https://tikhub.io 注册并拿 API Key"
        verify: "echo $TIKHUB_API_KEY 非空"
```

3. **`omnireach/cli.py`**: `_BOOSTER_KEY_ENV` 加 `"tikhub": "TIKHUB_API_KEY"`

4. **`omnireach/doctor.py`**: `ENV_FOR_BOOSTER` 同步加

5. **`omnireach/commands/setup.py`**: `BOOSTER_GUIDES` 加 tikhub:
```python
"tikhub": {
    "env": "TIKHUB_API_KEY",
    "signup_url": "https://tikhub.io",
    "label": "TikHub.io (抖音/TikTok/小红书/微博 等多平台付费 API)",
    "note": "按调用计费;500+ endpoints 覆盖多平台",
},
```

6. **tests**: copy `tests/adapters/test_tavily.py` 改名 + 改 env var + 改 fixture (用真实 TikHub response shape)

7. **README**: §💎 付费 booster 章节加 `omnireach setup tikhub` 一行 + 在源表加 tikhub 行

8. **bump 版本 → 0.7.0-alpha**

9. **PR + 标 fixes #12** → squash merge + tag + GitHub release

10. **issue #12 ping 反馈**: `gh issue comment 12 -b "v0.7.0-alpha ship 了,跑 omnireach setup tikhub 拿 Key 试一下;欢迎反馈"` 然后 close

### 关键技术验证 (spec 阶段必须做)

按 [[feedback-no-halfassing-search]] 教训:**别凭印象写 endpoint URL**

- [ ] 用 `curl` 真实打一次 TikHub 抖音 search endpoint,确认 request body / response shape
- [ ] 确认 freeform keyword 真能 work (不是只 hashtag / user_id)
- [ ] 确认 401/429/5xx 错误码语义
- [ ] 确认有 free trial / dev tier 让我们能 ship 前测一次

如果发现 TikHub 实际不行(很贵 / 拒绝某些 query / response shape 怪),fallback 用 OpenCLI douyin hashtag 路径,但要更新 issue 说明降级原因。

---

## §4 已知技术债 / 不在 v0.7 的事

放着不动直到有用户报或自己有动力做:

- **真 e2e CI matrix** (装真 yt-dlp/gh/rdt-cli/opencli docker images):lesson 7,目前都是 mock 测试
- **`omnireach diagnose --autopr`** (用户 agent 自动 fix upstream bug 后自动 PR 回 repo):v1.x wishlist
- **Marketplace 发布** (Claude Marketplace + PyPI):v1.0 才做
- **xiaohongshu 切 xhs-cli** (agent-reach 推荐路径,现有 OpenCLI 已工作,不紧急)
- **Windows 实测** (没机器,等用户 issue)
- **bilibili / wechat 真实质量验证** (Exa domain-filtered 抓 SPA 的 metadata 质量未知,无人投诉就不动)

---

## §5 这次 session 学到的产品/沟通教训

### 1. 不要把方向决策推给 user (本次 session 末尾被纠正)

issue #12 我两次回复都在罗列 3-5 个候选 + 问 menoking "你想走哪条 / 你能不能贡献 PR / 你有没有 Key"。**用户提 issue 是来报需求的,不是来做技术决策的**。正确做法:自己调研 → 自己拍方向 → 一句话告诉他「会做、方向 X、v0.7 ship 时 ping 你」。

被 user 直接喊停 + 要求撤回那两条回复。修正后的 comment 在 issue #12 当前唯一一条 (id 4544261931)。

### 2. 写资料别糊弄,该 search 就 search ([[feedback-no-halfassing-search]] 又踩了)

本次 session 我犯过两次幻觉:
- 第一次说 "Exa domain-filtered (`site:douyin.com`) 可以做抖音"——没验证抖音 SPA metadata 质量
- 第一次推荐 "douyin-mcp-server via mcporter" 当抖音 search 路径——没读 README,实际它只做 URL → 视频文案提取

第二次回复修正后才去 GitHub 真实搜了 5 个候选 + WebFetch 各自 README,锁定 **TikHub.io 是唯一靠谱的零部署 freeform search 路径**。

下次 session 写任何 spec 前,**至少 WebSearch + WebFetch 一次主候选**,别脑补 API 接口。

### 3. 真用户暴露的 v0.1 起 architecture bug

本次 session 跑 `omnireach search "vibe coding"` 测试时,发现 v0.1-v0.4 的 6 个 wrapper adapter (web/youtube/github/rss/wechat/bilibili) 调用的 `agent-reach <source> search` 子命令**根本不存在**。Agent-Reach v1.x 是 installer/doctor,不是 search proxy。

教训写进了 `docs/retrospectives/2026-05-26-v0.3-v0.5-lessons.md`,7 条 lessons,4 个 v0.6 action items 已全部 ship 进 v0.6.0-alpha。

### 4. 这个 session 的甲方模式形成

用户授权过 "PR 一气呵成" + "中间别问我了,UX 痛点再让我决策"。本次 session 我 ship 了 8 个版本 (v0.4 → v0.6.3) 期间问了 ~5 次甲方决策,都是真 scope/UX 级的 (例: v0.4 范围、付费 Key 默认行为、v0.5 web 源策略、v0.6 范围、Windows 是否做)。其他全部自决。

### 5. README 不能撒谎

v0.1 起 README 写「`omnireach init` 自动装好 agent-reach 等零配置依赖」是错的 (agent-reach 在 v0.1-v0.4 期间从未真正被 omnireach runtime 调用,且 pipx 不一定在用户机器上)。v0.5 ship 时改成诚实版本,但 init.py 死代码留到 v0.6.1 才清干净。

---

## §6 进入下个 session 的第一件事

1. `cd ~/Projects/omnireach`
2. `git pull` (拿到这份 handoff 和 main 上其他可能的变更)
3. `cat docs/handoff/2026-05-26-session-handoff.md` (这份文档)
4. `gh issue view 12` (看 menoking 有没有回评论;如果回了,看他补充信息)
5. **直接开 v0.7 spec** (`docs/superpowers/specs/2026-XX-XX-tikhub-douyin.md`),不再问 user 方向
6. 跑 plan → subagent-driven-development → ship,跟 v0.4-v0.6 节奏一致
7. ship 后 `gh issue comment 12 -b "..." && gh issue close 12`

记得整个流程不要 ship 前先 `curl https://api.tikhub.io/...` 真打一次抖音 search endpoint,验证响应 shape。

---

## §7 关键链接 (复制粘贴用)

- Repo: https://github.com/Daily-AC/omnireach
- Issue #12: https://github.com/Daily-AC/omnireach/issues/12
- v0.7 milestone: https://github.com/Daily-AC/omnireach/milestone/1
- TikHub Swagger: https://api.tikhub.io/
- TikHub Python SDK 参考: https://github.com/TikHub/TikHub-API-Python-SDK
- 主 spec: `docs/superpowers/specs/2026-05-25-omnireach-design.md`
- v0.5 retro: `docs/retrospectives/2026-05-26-v0.3-v0.5-lessons.md`
- 历史 plans: `docs/superpowers/plans/2026-05-25-omnireach-v0.{1,2,3,4}.md` + `2026-05-26-omnireach-v0.{5,6}.md`

---

**作者**: 2026-05-26 session 收尾 (~21:10)
**下次 session 接力时**: 把本文 §3 的 spec 检查项跑完即可直接 ship v0.7.0-alpha
