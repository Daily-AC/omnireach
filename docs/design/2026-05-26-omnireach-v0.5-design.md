# omnireach v0.5 设计

**日期**: 2026-05-26
**前序**: v0.1–v0.4 已上线，主 spec 见 `2026-05-25-omnireach-design.md`，v0.4 spec `2026-05-25-omnireach-v0.4-design.md`。
**触发**: 2026-05-26 v0.4 发布当晚跑 `omnireach search "vibe coding"` 时发现 6 个 wrapper adapter（web/youtube/github/rss/wechat/bilibili）调用的 `agent-reach <source> search ...` 接口在真实 Agent-Reach v1.4.0 中**根本不存在**。该 bug 自 v0.1 起一直存在，仅 hackernews（直连 Algolia）和 v0.4 三个 booster 真正可用。

## §0 一句话定义

v0.5 重写所有 wrapper adapter 为直接调上游 binary（yt-dlp / gh / rdt-cli / feedparser），把 Agent-Reach 严格收回 installer / doctor 定位，把 web search 降级成 booster（Exa）。

## §1 v0.4 的根因 bug

主 spec §5 假设「Agent-Reach (Python CLI, pipx install) → web/youtube/github/rss/wechat/bilibili/reddit」是个 search proxy，可以 `agent-reach <source> search <query>`。事实：

- `pip install agent-reach` 失败（不在 PyPI；正确装法 `uv tool install git+https://github.com/Panniantong/Agent-Reach.git`）
- Agent-Reach v1.4.0 子命令只有 `{setup, install, configure, doctor, uninstall, skill, format, check-update, watch, version}`，**无 `search`、无 `youtube`、无 `web` 等子命令**
- 真实定位：「installer + doctor + agent skill bootstrapper」—— 它装好上游工具（yt-dlp / gh / rdt-cli / mcporter+Exa），写一份 SKILL.md 教 AI agent **直接调上游 binary**，自己不转发 search

omnireach v0.1–v0.4 误把它当作 search proxy 来用，所以 6/9 个号称 ready/one_step 的源在任何用户机上都跑不了。

## §2 甲方决策（已锁定 2026-05-26）

| 项 | 决定 | 备注 |
|---|---|---|
| 修复路线 | **v0.5 重写 adapter，直接调上游 binary；Agent-Reach 仅作 installer wrapper** | 不走 hotfix-标 broken；不联系上游加 search 子命令 |
| `web search` 源 | **降级成 booster (Exa)**，需 `EXA_API_KEY` | 零配置 web search 在物理上不存在；现有 Tavily/Brave/Perplexity 已能兜底 |
| 第三方 MCP / 代理源 | **wechat / bilibili 推到 v0.6**，v0.5 标 tier `wip` 不参与 auto fanout | 保 v0.5 三天内 ship |
| v0.5 ready 源 | **yt-dlp / gh / rdt-cli / feedparser 四件** 走零配置直调 | reddit 仍归 one_step（rdt login 是一次性配置） |

## §3 目标 / 非目标

### v0.5 目标

1. 删除所有 `subprocess.run(["agent-reach", source, "search", ...])` 调用
2. 每个 adapter 用对应上游 binary 的真实 search API
3. `omnireach setup <source>` 重写：不再 `pipx install agent-reach`；改成各源单独装上游
4. `omnireach doctor` 重写：检测真实 binary 在 PATH，不依赖 agent-reach
5. 新增 `exa` booster adapter（web search）
6. README 改成诚实的部署说明，列上游 binary 依赖
7. 一份从零部署能跑通的 macOS smoke test 脚本

### 非目标

- wechat / bilibili 重写（推 v0.6）
- twitter / xiaohongshu 改造（保 v0.3 OpenCLI 路径不动）
- 自动包管理跨平台（macOS only；Linux best-effort）
- `pipx` 全局可用性问题（建议文档里推荐 `uv tool install`，但不强制）

## §4 架构变更

### v0.4 → v0.5 adapter 调用模型

| Adapter | v0.4 调用 | v0.5 调用 | upstream binary |
|---|---|---|---|
| hackernews | httpx → Algolia | **不变** | none (HTTP API) |
| youtube | `agent-reach youtube search` ❌ | `yt-dlp ytsearch10:"<q>" --flat-playlist --dump-json` | `yt-dlp` (pip install) |
| github | `agent-reach github search` ❌ | `gh search repos/issues "<q>" --json ...` | `gh` (brew/apt) |
| reddit | `agent-reach reddit search` ❌ | `rdt-cli search "<q>" --json --limit N` | `rdt-cli` (pip install) + `rdt login` |
| rss | `agent-reach rss …` ❌ | Python `feedparser` 直接 import | `feedparser` (pip) |
| web | `agent-reach web search` ❌ | **降级 booster**: httpx → Exa API | `EXA_API_KEY` env |
| wechat | `agent-reach wechat …` ❌ | tier `wip`, 不参与 fanout | (v0.6) |
| bilibili | `agent-reach bilibili …` ❌ | tier `wip`, 不参与 fanout | (v0.6) |
| twitter | OpenCLI bridge | **不变** | OpenCLI (v0.3) |
| xiaohongshu | OpenCLI bridge | **不变** | OpenCLI (v0.3) |
| tavily / brave / perplexity | httpx → API | **不变** | env var (v0.4) |

### 新 tier `wip`

`sources.yml` 引入：

| Tier | emoji | 含义 |
|---|---|---|
| `ready` | ✅ | 零配置 |
| `one_step` | 🟡 | 一次配置（rdt login 等） |
| `heavy` | 🔴 | Chrome 扩展 + 浏览器登录态 |
| `booster` | 💎 | 付费 API Key |
| **`wip`** | **🚧** | **接口待实现/待修复，v0.6+** |

`wip` 源 `default_in_auto: false`，`omnireach sources` 显示但 fanout 不调。

### Agent-Reach 的新角色

- 不再被 omnireach **运行时**调用
- **可选** 作为 `omnireach setup --batch` 的 installer 一键引导（跑 `agent-reach install --channels youtube,github,reddit`），但 doctor / adapter 均不依赖它
- README 把它列为「上游工具一键引导器」推荐项，不是必装

## §5 Adapter 详设计

### 5.1 `omnireach/adapters/youtube.py`

```python
class YouTubeAdapter(AdapterBase):
    name = "youtube"
    requires = ["yt-dlp"]

    async def is_ready(self) -> bool:
        return shutil.which("yt-dlp") is not None

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not shutil.which("yt-dlp"):
            raise AdapterUnavailable("youtube", "yt-dlp not installed",
                                     hint="omnireach setup youtube")
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", f"ytsearch{limit}:{query}",
            "--flat-playlist", "--dump-json", "--no-warnings",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise AdapterUnavailable("youtube", stderr.decode().strip())
        results: list[SearchResult] = []
        for line in stdout.decode().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            results.append(SearchResult(
                source="youtube", adapter="yt-dlp",
                title=entry.get("title") or "",
                url=entry.get("url") or entry.get("webpage_url") or "",
                content="",
                author=entry.get("uploader"),
                ts=_unix_to_iso(entry.get("timestamp")),
                engagement=Engagement(views=entry.get("view_count")),
                raw=entry,
            ))
        return results
```

### 5.2 `omnireach/adapters/github.py`

`gh search repos` + `gh search issues` 两路 fanout 内合并（限制 limit//2 each），按 stars / updatedAt 排序。

### 5.3 `omnireach/adapters/reddit.py`

```python
proc = await asyncio.create_subprocess_exec(
    "rdt-cli", "search", query, "--json", "--limit", str(limit),
    ...
)
```

`requires = ["rdt-cli"]`；若 binary 在但没 login（`rdt-cli` 返回特定 error），抛 `AdapterUnavailable` 提示 `rdt login`。

### 5.4 `omnireach/adapters/rss.py`

不走 subprocess，直接 `import feedparser`。`requires = []`（feedparser 进 `pyproject.toml` 的核心依赖，~50KB）。RSS adapter 接受的 query 是 URL — 解析后返回最近 N 条 entry。**这个 adapter 的语义跟其他 search 不一样**：query 必须是 URL。Router 应该只在 `query` 形如 URL 时 (regex `^https?://`) 把 rss 路由进去；否则跳过。

### 5.5 `omnireach/adapters/exa.py` (新增 booster)

```python
class ExaAdapter(AdapterBase):
    name = "exa"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bool(os.environ.get("EXA_API_KEY"))

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        key = os.environ.get("EXA_API_KEY")
        if not key:
            raise AdapterUnavailable("exa", "EXA_API_KEY 未设置",
                                     hint="omnireach setup exa")
        headers = {"x-api-key": key, "Content-Type": "application/json"}
        body = {"query": query, "numResults": limit, "type": "auto"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("https://api.exa.ai/search", json=body, headers=headers)
        # ... 401/429/5xx → AdapterUnavailable
        # ... results[*].title, url, publishedDate, text → SearchResult(cost="paid")
```

trust 0.85（与 Tavily 同档）。

### 5.6 wechat / bilibili — tier 改 `wip`

仅修改 sources.yml：

```yaml
- id: wechat
  tier: wip
  adapter: omnireach.adapters.wechat.WeChatAdapter
  description: 微信公众号 (v0.6 重写, 需 Exa MCP)
  default_in_auto: false
  trust: 0.55
- id: bilibili
  tier: wip
  adapter: omnireach.adapters.bilibili.BilibiliAdapter
  description: B站视频 (v0.6 重写)
  default_in_auto: false
  trust: 0.55
```

adapter 代码暂保留（注释 deprecated），但既然 `default_in_auto=false`，跑搜索时不会被打开。

## §6 setup wizard 重写

### 6.1 删除统一 agent-reach install 路径

`omnireach/commands/setup.py` 不再 `subprocess.run(["pipx", "install", "agent-reach"])`。

### 6.2 每源独立路径

| `omnireach setup <X>` | 行为 |
|---|---|
| `youtube` | 检测 `yt-dlp`；没有 → 跑 `pip install yt-dlp`（用当前 Python 环境）；doctor 校验 |
| `github` | 检测 `gh`；没有 → 提示 macOS: `brew install gh`，Linux: 链接到 cli.github.com；不自动装系统包 |
| `reddit` | 检测 `rdt-cli`；没有 → `uv tool install rdt-cli` 或 `pip install rdt-cli`；装好后引导跑 `rdt login` |
| `rss` | no-op（feedparser 是 omnireach 自带依赖） |
| `web` | 提示「v0.5 起 web search 走 booster；要么配 EXA_API_KEY，要么用 Tavily/Brave/Perplexity」并打开下一步 |
| `exa` | 类似 `setup tavily`：拿 Key + 写 `~/.omnireach/secrets.env` |
| `tavily / brave / perplexity` | **不变**（v0.4 已就绪） |
| `twitter / xiaohongshu` | **不变**（v0.3 OpenCLI） |
| `wechat / bilibili` | 打印「v0.6 重写中，敬请期待；当前不可用」并退出 |

### 6.3 新增 `omnireach setup --batch`

一键引导 agent-reach install 4 个 ready 源（不强制）：

```bash
omnireach setup --batch
# 提示: 我们会跑 `agent-reach install --channels youtube,github,rss,reddit` 来装上游, 继续吗?
```

如果用户没装 agent-reach，会先 `uv tool install git+...Agent-Reach.git`。

## §7 doctor 重写

`omnireach/doctor.py`：

- 逐源检查 `shutil.which(binary)` + 各源轻探活（HN 跑 Algolia ping、Exa 跑 Key 探测、yt-dlp 跑 `yt-dlp --version`）
- 输出表：源 / tier / binary / 状态 / 修复建议（直接给 `omnireach setup <X>` 命令）
- 不调任何 `agent-reach` 命令

## §8 文件变更清单

新增：
- `omnireach/adapters/exa.py`
- `tests/adapters/test_exa.py`
- `tests/adapters/test_youtube.py`（重写覆盖）
- `tests/adapters/test_github.py`（重写）
- `tests/adapters/test_reddit.py`（重写）
- `tests/adapters/test_rss.py`（重写）
- `scripts/smoke_v0.5.sh`（从零部署 smoke）

重写：
- `omnireach/adapters/youtube.py`
- `omnireach/adapters/github.py`
- `omnireach/adapters/reddit.py`
- `omnireach/adapters/rss.py`
- `omnireach/commands/setup.py`
- `omnireach/doctor.py`

修改：
- `omnireach/sources.yml`（web→booster、新增 exa、wechat/bilibili→wip、移除 `pipx install agent-reach` deps）
- `omnireach/commands/sources.py`（加 🚧 wip tier 渲染）
- `omnireach/router.py`（rss 路由仅在 query 看起来是 URL 时启用）
- `omnireach/installer.py`（删除 / 极简，agent-reach 可选）
- `README.md`（诚实的部署章节）
- `pyproject.toml`（feedparser 加进核心 deps）

删除/弃用：
- `omnireach/adapters/wechat.py` 与 `omnireach/adapters/bilibili.py` 的 search 代码注释成 deprecated 占位

## §9 测试策略

| 模块 | 测试 |
|---|---|
| youtube / github / reddit | mock `asyncio.create_subprocess_exec` 跑 success / empty / non-json / nonzero exit / binary missing |
| rss | feedparser fixture (本地 .xml)、URL 非 URL 时跳过 |
| exa | httpx mock，跟 tavily/brave/perplexity 同模板 |
| doctor | mock `shutil.which`，断言每源状态正确 |
| router | URL 形 query → rss 入选；非 URL → rss 不入选 |
| smoke | bash 脚本：`omnireach setup --batch`（mock，离线）→ `omnireach doctor` 输出包含 4 ready ✓ |

## §10 非目标（v0.6+）

- wechat → Exa MCP via mcporter（需 npm + Exa Key）
- bilibili → 调研真实上游（agent-reach 也走 Exa + 代理）
- jina-reader 作为 read-URL adapter（不是 search，需要先理顺 omnireach 的 read vs search 语义）
- 跨平台自动装 gh（Windows / Linux）
- agent-reach 完全可选化（不依赖任何外部 installer）

## §11 风险

| 风险 | 缓解 |
|---|---|
| `yt-dlp` 输出格式变 | 写 fixture 测；锁版本 hint（pyproject `[project.optional-dependencies]` 给 pin 范围） |
| `gh` 用户 unauth | doctor 检测 `gh auth status`，未登录 → `omnireach setup github` 引导 |
| `rdt-cli` API 变 | reddit adapter 加 schema 容错（缺字段忽略） |
| feedparser 依赖增重 | 实测 ~150KB，可接受 |
| 用户已经按 v0.4 README 跑了 `omnireach setup web` 死循环 | v0.5 README 顶部加 migration note：「v0.5 起 web 走 booster；之前装的 agent-reach 不删」 |

## §12 决策追踪

| 决策 | 选项 | 选定 | 理由 |
|---|---|---|---|
| 修复策略 | hotfix doc / 重写 adapter / 联系上游 | **重写 adapter** | 用户原话 + 项目尚未公开主推，重写代价合理 |
| web 源 | 保 ready+DDG / 双结构 / 降级 booster | **降级 booster** | 零配置 web search 物理上不存在；已有 booster 兜底 |
| v0.5 scope | 4 件 / +Exa MCP wechat / 全梳 | **4 件 (yt-dlp/gh/rdt-cli/feedparser)** | 三天内 ship；wechat/bilibili 推 v0.6 |
| Agent-Reach 依赖度 | 必装 / 可选 / 完全甩开 | **可选**（`omnireach setup --batch` 调用，但 runtime 不依赖） | 保留 onboarding 便利，剪掉 runtime 耦合 |
| feedparser 引入方式 | runtime dep / extras / subprocess | **runtime dep** | 体积小、行为可控、不被外部 binary 卡 |
