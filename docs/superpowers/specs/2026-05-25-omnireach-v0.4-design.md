# omnireach v0.4 设计

**日期**: 2026-05-25
**前序**: v0.1 / v0.2 / v0.3 已上线（10 源 / 3 tier），主 spec 见 `2026-05-25-omnireach-design.md`。
**本档作用**: 主 spec §12 把 v0.4 锁为「付费 booster + 评分小改」，本档补 preferences 偏好层一项，并把三块的实施细节落到可写 plan 的粒度。

## §0 一句话定义

v0.4 给 omnireach 加三件事：检测式接入付费搜索 booster（Tavily / Brave / Perplexity）、用户偏好层 `~/.omnireach/preferences.toml`、source_trust 加权的 ranking。

## §1 甲方决策（本里程碑新增）

| 项 | 决定 | 备注 |
|---|---|---|
| 本期范围 | **全做：booster + preferences + ranking 小改** | 一并发 v0.4.0-alpha |
| 付费 Key 默认行为 | **检测到即自动启用，结果元数据标注 `cost="paid"`** | 用户主动配 Key 视作 opt-in；TTY 显示 💎，JSON 加字段，便于 debug / 审计 |

主 spec §3 已锁的「免费优先 + 可选付费增强」「中文 first」「umbrella + 适配器壳」「分层 + 心愿单」继续遵循。

## §2 付费 booster

### 2.1 新增 tier

`sources.yml` 增加第四个 tier：

| Tier | emoji | 含义 |
|---|---|---|
| `ready` | ✅ | 零配置 |
| `one_step` | 🟡 | 一次 OAuth/Key |
| `heavy` | 🔴 | Chrome 扩展 + 浏览器登录态 |
| **`booster`** | **💎** | **付费 API Key，检测式接入** |

### 2.2 三家适配器

| 源 | 检测信号 | API 端点 | 默认 trust |
|---|---|---|---|
| `tavily` | `TAVILY_API_KEY` env | `POST https://api.tavily.com/search` | 0.85 |
| `brave` | `BRAVE_API_KEY` env | `GET https://api.search.brave.com/res/v1/web/search` | 0.80 |
| `perplexity` | `PERPLEXITY_API_KEY` env | `POST https://api.perplexity.ai/chat/completions`（model `sonar-pro`） | 0.90 |

实现路径：
- 新目录 `omnireach/boosters/`，三个单文件 adapter：`tavily.py` / `brave.py` / `perplexity.py`
- 全部走 Python + httpx，复用 v0.1 web adapter 的 client / retry / timeout 框架
- 每个 adapter 暴露同一个 `async def search(query: str, *, limit: int) -> list[SearchResult]` 签名
- 超时统一 5 秒；429 / 5xx 由 dispatcher 现有容错吃掉（失败该源标 degraded，不阻塞其他源）

### 2.3 Key 装配

- CLI 启动时先把 `~/.omnireach/secrets.env` 解析并写入 `os.environ`（不覆盖已有 env，进程环境优先）
- 然后每次 `omnireach search` 走 `os.environ.get(...)` 检测；命中即纳入 fanout
- dotenv 解析手写（一两行：split `=`、strip 引号），不引入 python-dotenv
- 文件权限：`secrets.env` 写入时强制 `chmod 600`；启动时若发现权限宽于 600，仅打 warning（不阻塞）

### 2.4 Setup wizard

新增三条 setup 路径，节奏与 v0.2 reddit 一致：

```
$ omnireach setup tavily
  Tavily 是付费 web 搜索 API（免费层每月 1000 次）。
  Agent 能做的：
   ✅ 打开拿 Key 的官网（https://tavily.com → Sign up）
   ✅ 把你粘贴的 Key 写入 ~/.omnireach/secrets.env（chmod 600）
  你需要做的：
   👤 注册 / 登录后，复制 Dashboard 里的 API Key 粘到这里
  开始吗? [Y/n]
```

Brave / Perplexity 同理，引导网址分别 `brave.com/search/api` 和 `perplexity.ai/settings/api`。

### 2.5 Sources 命令显示

```
$ omnireach sources

  ✅ ready (7):    web, youtube, hackernews, rss, github, 微信公众号, B站
  🟡 一步配置 (1): reddit
  🔴 重配置 (2):   twitter, 小红书
  💎 付费增强 (3): tavily (未配), brave (未配), perplexity (✓ 已配)
```

## §3 preferences 偏好层

### 3.1 文件位置 & schema

`~/.omnireach/preferences.toml`，pydantic v2 model 校验。加载失败时 fallback default 并打印 warning（不阻塞 search）。

```toml
[defaults]
on      = ["web", "hackernews", "reddit", "twitter"]   # --on 默认值
exclude = []                                            # 始终排除的源
lang    = "zh-CN"                                       # 透传到 web/wechat 等

[output]
format                 = "tty"   # tty | json
max_results_per_source = 8

[boosters]
auto_enable = true               # false = 检测到 Key 也不用

[trust_overrides]
# "web" = 0.8                    # 用户覆盖默认 source_trust
```

pydantic model 路径 `omnireach/preferences.py`，每段一个 `BaseModel`，根 `Preferences` 聚合。`pydantic-settings` 不引入（避免额外依赖），手写 toml load + validate。

### 3.2 加载顺序（高 → 低优先）

CLI flag → `preferences.toml` → `sources.yml` 默认 → hardcoded fallback

### 3.3 子命令

```
omnireach preferences show     # 打印当前生效配置（合并后）
omnireach preferences path     # 打印文件路径
omnireach preferences edit     # 用 $EDITOR 打开（fallback: vi）
omnireach preferences reset    # 覆盖回默认（先备份到 .bak）
```

`omnireach init` 首次运行时：若文件不存在，写入一份带注释的默认 `preferences.toml`。

## §4 ranking 小改

### 4.1 公式

```
score = 0.4 * recency_norm + 0.6 * source_trust
```

- `recency_norm`：`SearchResult.published_at` 归一化到 [0, 1]
  - 当批结果按时间排序后线性归一（最新 1.0、最旧 0.0）
  - 无时间戳的结果（如 HN comment、部分 RSS）取 0.5
- `source_trust`：从 `sources.yml` 的新 `trust` 字段读取，可被 `preferences.toml [trust_overrides]` 覆盖

### 4.2 默认 trust 表

| 源 | trust | 源 | trust |
|---|---|---|---|
| web (Jina) | 0.70 | github | 0.90 |
| hackernews | 0.85 | youtube | 0.60 |
| rss | 0.75 | 微信公众号 | 0.55 |
| reddit | 0.70 | B站 | 0.55 |
| twitter | 0.60 | 小红书 | 0.50 |
| **tavily** | **0.85** | **brave** | **0.80** |
| **perplexity** | **0.90** | | |

### 4.3 排序与 round-robin 关系

原 round-robin 仅保留为「同 score ±0.05 范围内打散源」的二级 tie-breaker，主排序按 score 降序。

## §5 SearchResult schema 变更

新增字段：

```python
class SearchResult(BaseModel):
    # ... existing
    cost: Literal["free", "paid"] = "free"
    raw_score: float = 0.0          # 排序前的 score，便于 debug / --json
```

TTY 渲染：`cost == "paid"` 时行首加 💎 prefix。
JSON 输出：原样保留 cost 与 raw_score 字段。

## §6 文件变更清单

新增：
- `omnireach/boosters/__init__.py`
- `omnireach/boosters/tavily.py`
- `omnireach/boosters/brave.py`
- `omnireach/boosters/perplexity.py`
- `omnireach/preferences.py`
- `omnireach/scoring.py`
- `tests/test_boosters_*.py`（×3）
- `tests/test_preferences.py`
- `tests/test_scoring.py`

修改：
- `omnireach/sources.yml`（新 tier `booster`、各源 `trust` 字段、3 个 booster 条目）
- `omnireach/schemas.py`（SearchResult 加 cost / raw_score）
- `omnireach/normalizer.py`（接 scoring 模块）
- `omnireach/cli.py`（新增 `preferences` 子命令、`setup tavily/brave/perplexity`、`sources` 输出 💎 段）
- `omnireach/wizard.py`（三家 booster setup 流程）
- `omnireach/dispatcher.py`（识别 booster tier + cost 字段透传）
- `README.md`（💎 tier 介绍、preferences.toml 示例）

## §7 测试策略

| 模块 | 测试形态 |
|---|---|
| boosters | mock httpx，对每家跑 200 success / 401 unauth / 429 rate-limit / timeout 四个 fixture |
| preferences | load valid / load invalid (schema 错) / load missing (fallback) / round-trip write+read |
| scoring | 单测公式：recency 边界 / trust override / 同分 round-robin tie-break |
| 集成 | 至少一个 E2E：mock env 配 `TAVILY_API_KEY` → `omnireach search` 含 💎 标记结果 |

## §8 非目标（明确推后）

| 项 | 推到 |
|---|---|
| usage tracking / monthly budget cap | v0.5+ |
| TUI 化的 preferences 编辑器 | 不做（`$EDITOR` 足够） |
| booster 召回去重（与 web Jina 结果合并） | v0.5+（先各走各的，靠 ranking 自然降权） |
| Tavily 的 `include_domains` / `topic` 高级参数 | v1.0+ |
| 团队 / 多机 preferences 同步 | 永不（个人工具） |

## §9 风险

| 风险 | 缓解 |
|---|---|
| 用户配 Key 测试一下就被持续扣费 | TTY / JSON 醒目标注 cost=paid；README 说明；`preferences.toml [boosters].auto_enable = false` 兜底 |
| booster API 限频 / 抖动拖慢 fanout | 5s 超时 + dispatcher 容错（继承 v0.1 机制）；失败不阻塞其他源 |
| pydantic v2 toml 反序列化坑 | 手写 `tomllib.loads` + 显式 `model_validate`，避开 pydantic-settings 依赖 |
| trust 数值主观，用户不爽 | 提供 `[trust_overrides]` 一键覆盖；README 提示「这是默认偏见，欢迎调」 |

## §10 决策追踪（本里程碑）

| 决策 | 选项 | 选定 | 理由 |
|---|---|---|---|
| 范围 | booster only / booster+prefs / 全做 | **全做** | 用户拍板，alpha 完整度优先 |
| 付费 Key 默认 | 自动启用 / 显式 opt-in / 自动+预算 | **自动启用 + cost 标注** | 配 Key 即 opt-in；预算推后 |
| toml 解析 | pydantic-settings / 手写 tomllib | **手写 tomllib + pydantic 校验** | 减依赖，行为可控 |
| 编辑器 | TUI / `$EDITOR` | **`$EDITOR`** | YAGNI |
| trust 数值 | 用户自评 / 我拍板默认 | **我拍板 + 允许覆盖** | 用户授权技术细节自决 |
