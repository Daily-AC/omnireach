# omnireach v0.6 设计

**日期**: 2026-05-26
**前序**: v0.5.2 已上线。Lessons retrospective: `docs/retrospectives/2026-05-26-v0.3-v0.5-lessons.md`
**触发**: lessons 4 个 action items + v0.5 spec §10 推迟的 wechat/bilibili 重写

## §0 一句话定义

v0.6 把 wechat/bilibili 从 wip 升级成「Exa-derived booster」（复用 v0.5 ExaAdapter 的 httpx 模板加 domain filter），同时落地 retrospective 的 4 个 UX/工程项。

## §1 甲方决策（已锁定 2026-05-26）

| 项 | 决定 | 备注 |
|---|---|---|
| v0.6 范围 | **全做：4 actions + wechat + bilibili** | 用户拍板 |
| wechat/bilibili 上游路径 | **直接 httpx 调 Exa API**（不通过 mcporter） | 复用 v0.5 ExaAdapter 框架；不引入新系统依赖；需 `EXA_API_KEY` |
| 新 tier 还是复用 booster | **复用 booster** | wechat/bilibili 当作 Exa 的 domain-filtered preset，逻辑上跟 tavily/brave/perplexity/exa 同档 |
| timeout 实现 | **sources.yml 加 `timeout_seconds` 字段** | dispatcher 用 per-source timeout，fallback CLI `--timeout`，fallback 全局 30s |
| dispatcher errors 分类 | **`AdapterUnavailable` → silent in TTY**；其他异常 → 红字 | JSON 输出保留所有 errors；TTY 加 footer "N 源未配置, 跑 omnireach doctor" |
| README 跨 CLI 兼容性 | **加 "Works with" 一行**（Claude Code / Antigravity / .claude-plugin 兼容 CLI） | lesson 5 |

## §2 wechat / bilibili 重写

### 2.1 上游路径

agent-reach 文档 (`~/.claude/skills/agent-reach/references/web.md` + `references/social.md`) 证实：
- **wechat**: Exa MCP 通过 `mcporter call exa.web_search_exa(query, numResults, includeDomains: ["mp.weixin.qq.com"])`
- **bilibili**: agent-reach 只示范 `yt-dlp --dump-json <URL>` 读单个视频，**没有 query → search 上游**

→ 两者都用 Exa Search API（domain-filtered），不通过 mcporter（避免引入 npm 依赖）。等于复用 v0.5 ExaAdapter 的 httpx 调用模板加 `includeDomains` 参数。

### 2.2 适配器实现

`omnireach/adapters/wechat.py`:

```python
class WeChatAdapter(AdapterBase):
    name = "wechat"
    requires: list[str] = []

    async def is_ready(self) -> bool:
        return bool(os.environ.get("EXA_API_KEY"))

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        # 跟 ExaAdapter 一样，但 body 加 includeDomains
        body = {"query": query, "numResults": limit, "type": "auto",
                "includeDomains": ["mp.weixin.qq.com"]}
        # ... rest mirrors ExaAdapter
        # source="wechat", cost="paid"
```

`omnireach/adapters/bilibili.py`: 同模式，`includeDomains: ["bilibili.com", "www.bilibili.com"]`。

### 2.3 sources.yml 变更

```yaml
- id: wechat
  tier: booster                  # 从 wip 升级
  adapter: omnireach.adapters.wechat.WeChatAdapter
  description: 微信公众号 (via Exa domain-filtered search, 需 EXA_API_KEY)
  query_hints: [微信, 公众号, wechat]
  default_in_auto: true
  trust: 0.65
  deps:
    auto: []
    manual:
      - step: "去 https://exa.ai 拿 EXA_API_KEY"
        verify: "echo $EXA_API_KEY 非空"

- id: bilibili
  tier: booster
  adapter: omnireach.adapters.bilibili.BilibiliAdapter
  description: B站视频/笔记 (via Exa domain-filtered search, 需 EXA_API_KEY)
  query_hints: [b站, bilibili, 哔哩哔哩]
  default_in_auto: true
  trust: 0.60
  deps:
    auto: []
    manual:
      - step: "去 https://exa.ai 拿 EXA_API_KEY"
        verify: "echo $EXA_API_KEY 非空"
```

### 2.4 CLI / Doctor 集成

`omnireach/cli.py` `_BOOSTER_KEY_ENV` 扩展：

```python
_BOOSTER_KEY_ENV = {
    "tavily": "TAVILY_API_KEY",
    "brave": "BRAVE_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "exa": "EXA_API_KEY",
    "wechat": "EXA_API_KEY",       # 共享 Exa Key
    "bilibili": "EXA_API_KEY",
}
```

`omnireach/doctor.py` `ENV_FOR_BOOSTER` 同步扩展。

注：用户配一个 EXA_API_KEY 就同时点亮 exa + wechat + bilibili 三个源。

### 2.5 wip tier 保留还是删？

**保留 tier 定义**（以后还会有新 wip 项），但 v0.6 后 sources.yml 里没有 tier=wip 的源。`omnireach sources` 渲染 wip 段时显示 "(无)" 或不显示该 section。

## §3 Per-source timeout（lesson 3）

### 3.1 sources.yml

每个源可选加 `timeout_seconds: <float>`：

```yaml
- id: hackernews
  timeout_seconds: 10    # HTTP API 很快
- id: youtube
  timeout_seconds: 20    # yt-dlp 可能慢
- id: twitter
  timeout_seconds: 30    # OpenCLI 唤起 Chrome
- id: xiaohongshu
  timeout_seconds: 30
```

未设字段 → 沿用 dispatcher 全局默认（30s）。

### 3.2 registry / dispatcher 接线

- `SourceSpec` 加 `timeout_seconds: float | None = None`
- `Dispatcher` 改造：per-adapter 各自包 `asyncio.wait_for(adapter.search(...), timeout=resolved_timeout)`
- 解析顺序：source.timeout_seconds → CLI `--timeout` → 全局 30s

### 3.3 CLI `--timeout` 含义变化

`--timeout` 现在是「未配 per-source 超时的源的 fallback」，不再是「全局上限」。Help string 改成：`"全局默认 timeout，被 sources.yml 中各源的 timeout_seconds 覆盖"`。

## §4 Dispatcher errors 分类（lesson 4）

### 4.1 错误分类

| 异常类型 | 分类 | TTY 行为 | JSON 行为 |
|---|---|---|---|
| `AdapterUnavailable` | `unavailable` | **silent**（不打红字） | `errors[]` 仍记录 `category: "unavailable"` |
| 其他 Exception | `failed` | **TTY 红字** `✗ {source}: {error}` | `errors[]` 记录 `category: "failed"` |
| TimeoutError | `failed` | TTY 红字 `✗ {source}: timeout` | `errors[]` `category: "failed"` |

### 4.2 TTY footer

如果 unavailable 数 > 0，TTY table 后加：
```
ℹ️  {N} 个源未配置（跑 `omnireach doctor` 查看修复建议）
```

### 4.3 SourceError schema 变更

`omnireach/contract.py`:

```python
class SourceError(BaseModel):
    source: str
    error: str
    category: Literal["unavailable", "failed"] = "failed"
```

dispatcher 在 raise/catch 时填 category 字段。

## §5 verify-adapter-contracts.sh（lesson 1+2）

`scripts/verify-adapter-contracts.sh`:

逻辑：
1. 遍历 adapter argv 静态列表（写死在 script 里：哪个 adapter 调哪个 binary 哪个子命令）
2. 对每个 `(binary, subcmd)` 跑 `<binary> <subcmd> --help`
3. 检查 adapter 用的 flag 是否出现在 help output 里（grep）
4. 不匹配则 stderr 报警 + exit 1（开发本地用，不在 CI 强制）

格式（伪代码）：

```bash
adapters=(
    "yt-dlp|ytsearch|--flat-playlist|--dump-json|--no-warnings"
    "gh|search repos|--json"
    "gh|search issues|--json"
    "rdt-cli|search|--json|--limit"
    "opencli|twitter search|--format|--limit"
    "opencli|xiaohongshu search|--format|--limit"
)

for entry in "${adapters[@]}"; do
    IFS='|' read -r binary subcmd flags <<< "$entry"
    if ! command -v "$binary" >/dev/null; then
        echo "⏭️  $binary not installed, skipping"
        continue
    fi
    help_out=$("$binary" $subcmd --help 2>&1 || true)
    for flag in $flags; do
        if ! echo "$help_out" | grep -q -- "$flag"; then
            echo "❌ $binary $subcmd: flag '$flag' not found in --help"
        fi
    done
done
```

开发流程文档：每次 release candidate 跑一次。CI 不强制（CI 没装 opencli 等）。

## §6 README cross-CLI 兼容性（lesson 5）

README 顶上 features 列表加：

```markdown
- **Works with**: Claude Code / Antigravity (`agy`) / 任何识别 `.claude-plugin/` manifest 的 CLI。
  v0.5.1 实测过 agy plugin install → SKILL 路由触发完整 work。
```

## §7 文件变更清单

新增 / 重写:
- `omnireach/adapters/wechat.py`（重写）
- `omnireach/adapters/bilibili.py`（重写）
- `tests/adapters/test_wechat.py`（重写）
- `tests/adapters/test_bilibili.py`（重写）
- `scripts/verify-adapter-contracts.sh`

修改:
- `omnireach/sources.yml`：wechat/bilibili wip→booster，每源加 timeout_seconds
- `omnireach/registry.py`：SourceSpec 加 `timeout_seconds: float | None = None`
- `omnireach/contract.py`：SourceError 加 `category: Literal["unavailable","failed"] = "failed"`
- `omnireach/dispatcher.py`：per-source timeout + 错误分类
- `omnireach/cli.py`：_BOOSTER_KEY_ENV 加 wechat/bilibili 共享 EXA_API_KEY；TTY 渲染只打 failed、加 footer；--timeout help 改
- `omnireach/doctor.py`：ENV_FOR_BOOSTER 同步
- `omnireach/commands/sources.py`：wip section 渲染为「(无)」when empty
- `omnireach/commands/setup.py`：wechat / bilibili 不再走 `_setup_wip`，改成 booster 路径（提示用户配 EXA_API_KEY）
- `README.md`：加 "Works with" 一行
- `pyproject.toml` + `omnireach/__init__.py`：版本 → 0.6.0-alpha
- 测试：test_registry / test_router / test_doctor / test_cmd_setup / test_cmd_sources 同步

## §8 测试策略

| 模块 | 测试 |
|---|---|
| wechat adapter | httpx mock + `includeDomains` 断言；is_ready 真假；401/429 |
| bilibili adapter | 同上 |
| timeout | mock 一个慢 adapter (sleep 远超 timeout) + 设 source.timeout_seconds=0.1，断言 TimeoutError 分类 failed |
| dispatcher 错误分类 | AdapterUnavailable → category=unavailable；ValueError → failed |
| TTY footer | CliRunner 跑一次有 unavailable 的 search，断言 footer 出现 |
| verify-adapter-contracts.sh | bash 单测：mock 个 `gh` binary 写 help 输出，跑 script，断言 grep 通过 |

## §9 非目标（v0.7+）

- xiaohongshu 切换到 xhs-cli（agent-reach 推荐路径），目前 OpenCLI 已能 work，不动
- bilibili 真正的「query → video list」（需要爬虫 / B 站 search API 反向工程）
- mcporter 集成（直接 httpx 调 Exa 更轻，避免 npm 依赖）
- 跨平台 setup（Linux/Windows 装 gh）
- 真实 e2e CI matrix（lesson 7，需要装 yt-dlp/gh/rdt-cli/opencli docker images）

## §10 决策追踪

| 决策 | 选项 | 选定 | 理由 |
|---|---|---|---|
| wechat/bilibili 路径 | mcporter / 直接 httpx Exa / 反爬 | **直接 httpx Exa** | 复用 ExaAdapter 模板；不引入 npm；不打反爬猫鼠游戏 |
| 复用还是新 tier | 复用 booster / 新 derived tier | **复用 booster** | wechat/bilibili 跟 exa 共享 Key，逻辑同档；不让 UI tier 数膨胀 |
| timeout 字段位置 | sources.yml / pyproject.toml / dispatcher 常量 | **sources.yml** | 跟 trust 同位，运维可改不需要重 build |
| `AdapterUnavailable` 在 TTY 红字 | 还是 silent | **silent** | 真用户当晚抱怨过 5 个 ✗ red errors 的噪音；doctor 是查 unconfigured 的入口 |
