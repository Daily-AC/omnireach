# omnireach v0.9.0-alpha — free-tier wechat + bilibili (Sogou / B站 API), Exa stays as opt-in enhancement

Date: 2026-05-27
Status: approved (3 甲方决策 locked 2026-05-27 在 brainstorm 中)
Version target: `v0.9.0-alpha`

## 1. Background

CLAUDE.md v0.8 候选 list 中：

> Scrapling 给 wechat/bilibili 做"无 EXA Key 也能跑"的免费降级路径

v0.7 起 wechat 与 bilibili 强依赖 `EXA_API_KEY` (💎 booster tier)。没 Key 的中转站 Agent 用户拿不到这两个源 —— 而这恰恰是 omnireach 服务的核心人群。v0.9 解锁免费路径。

v0.8.0 → v0.8.1 hotfix 的 E2E 教训也直接影响本次设计：原以为"用 Scrapling"的 spec 在 viability spike 中发现 Scrapling 即便基础 Fetcher 也强拖 playwright（~80MB）。E2E 实测纯 `httpx + lxml` 就能拿 Sogou SERP，B站官方 search API 直接返 JSON 无 cookie。简化方案。

## 2. 甲方决策（2026-05-27 brainstorm 锁）

1. **技术栈**: C — 双轨 `httpx` 作 default + `scrapling` 可选增强（只对 wechat/Sogou 有意义；bilibili JSON API 不需要）
2. **范围**: 2 — wechat + bilibili 一并做（CLAUDE.md 原候选措辞）
3. **共存模型**: α — 单 source `wechat` / `bilibili` 双后端；优先级 Exa > Sogou/B站API；现有 Exa 用户零变化

## 3. 设计

### 3.1 双后端 priority（wechat 与 bilibili 同 pattern）

```
wechat.search(query):
    if EXA_API_KEY 在环境里:
        try _exa_backend.search() → 返
        except (AdapterUnavailable | upstream error):
            log warn, 落 Sogou
    return _sogou_backend.search()

bilibili.search(query):
    if EXA_API_KEY 在环境里:
        try _exa_backend.search() → 返
        except (AdapterUnavailable | upstream error):
            log warn, 落 B站 API
    return _bilibili_api_backend.search()
```

**Why Exa 优先**：CLAUDE.md "降级路径" 措辞 + Exa 有语义搜索质量优势 + 现有付费用户零打扰。

**fallback 触发条件**: Exa 抛 `AdapterUnavailable`（401/429/5xx）→ 不要默默吞掉 Exa 错误，要在 stderr/log warn 一句，方便 doctor 诊断。

### 3.2 Sogou wechat backend

URL: `https://weixin.sogou.com/weixin?type=2&query=<urlencoded>&ie=utf8`

- HTTP only, 无 cookie 需求
- Headers: Chrome UA + `Accept-Language: zh-CN`
- 解析: `lxml` + cssselect
- 选择器（E2E 2026-05-27 验证）:
  | 字段 | 选择器 |
  |---|---|
  | item | `.news-list li` |
  | title | `.txt-box h3 a` → `text_content()`（剥 `<em>` 高亮标签） |
  | snippet | `.txt-box p.txt-info` → `text_content()` |
  | account | `.s-p .all-time-y2` → `text_content()` |
  | timestamp | `.s-p .s2 script` 内文 `timeConvert('<unix_ts>')` 中正则提 ts |
  | link | `.txt-box h3 a[href]` → `https://weixin.sogou.com` + 该相对路径（保留 Sogou redirect, 不主动 follow） |
- Link 不主动跟随重定向 —— Sogou `/link?url=...` 在浏览器/omnifetch 里点开能正常跳到 `mp.weixin.qq.com`，主动 follow 会多一次请求且容易触发 anti-bot
- `engagement` 全 None（Sogou SERP 不返）
- `cost="free"`

### 3.3 Scrapling optional enhancement (wechat 唯一)

`omnireach/adapters/_wechat_sogou.py` 顶部:

```python
try:
    from scrapling.fetchers import StealthyFetcher  # type: ignore
    _STEALTHY = StealthyFetcher
except ImportError:
    _STEALTHY = None
```

- `_STEALTHY` 为 None → 走 `httpx` 路径（default）
- `_STEALTHY` 可用 → 用 `StealthyFetcher` (Camoufox/Playwright stealth) 抓取
- 用户 `pip install scrapling[fetchers]` 或类似命令后自动启用
- Doctor 检测 Scrapling 是否可用，sources 列出"Scrapling enhanced"hint

### 3.4 Bilibili API backend

URL: `https://api.bilibili.com/x/web-interface/search/all/v2?keyword=<urlencoded>`

- HTTP only, 无 cookie, 必须带 `Referer: https://search.bilibili.com/`
- 返 JSON: `{code:0, data:{result:[{result_type:"video", data:[…20…]}, …]}}`
- 我们只取 `result_type == "video"` block，丢弃其他（bangumi/live 等不在 omnireach 视频搜索 scope）
- 字段映射:
  | omnireach | bilibili JSON |
  |---|---|
  | title | `title`（剥 `<em class="keyword">` 标签） |
  | url | `https://www.bilibili.com/video/{bvid}` |
  | content | `description`（截 500 字由 contract validator 自动处理） |
  | author | `author` |
  | ts | `pubdate`（unix 整数 → ISO 8601） |
  | engagement.likes | `like` |
  | engagement.views | `play` |
  | engagement.comments | `review` |
  | raw | 整个 video item dict |
- `cost="free"`

### 3.5 Tier 调整

`sources.yml` 中 wechat 与 bilibili `tier`:
- 从 `booster` → `ready`
- 增 `enhanced_with: EXA_API_KEY`（YAML 自由 metadata，不破坏现有 SourceSpec schema）—— TTY 显示 hint "EXA_API_KEY 可选启用语义搜索增强"
- `--mode quick` 默认会拉 ready 源 → wechat/bilibili 不应被默认拉进 quick（搜起来 ~3s 太慢）
  - 给两源加 `default_in_quick: false` 元数据（或简单地 router 跳过非 hackernews/web 的 ready 源 in quick mode）

### 3.6 不做的事（YAGNI）

- 不做 wechat 的 account search (`type=1`)，只做 article search (`type=2`)
- 不抓 article 全文（仍是 search 层，全文留给 omnifetch）
- 不实现 Sogou cookie pool / proxy rotation（先看会不会被 rate-limited，问题出现再说）
- 不做 bilibili 的其他 search_type (live/article/bangumi)
- 不并发取 Exa + free fallback 比较结果 — 串行 try-then-fallback

## 4. 文件清单

**修改**:
- `omnireach/adapters/wechat.py` — orchestrator: 优先 Exa, 失败 fallback Sogou
- `omnireach/adapters/bilibili.py` — orchestrator: 优先 Exa, 失败 fallback B站 API
- `omnireach/sources.yml` — wechat/bilibili tier booster→ready, enhanced_with 元数据
- `omnireach/registry.py` — `SourceSpec` 加可选 `enhanced_with: str | None = None` 字段
- `omnireach/doctor.py` — wechat/bilibili 状态显示考虑双后端（如果 Sogou/B站 API 也通就显示 ✅，EXA_API_KEY 缺只显示 hint 而非 ❌）
- `omnireach/cli.py` — TTY 输出对 `enhanced_with` 字段加 hint
- `tests/adapters/test_wechat.py` — 重写：测两个 backend + priority 逻辑 + fallback 触发
- `tests/adapters/test_bilibili.py` — 同上
- `tests/test_registry.py` — `enhanced_with` 字段 round-trip
- `tests/test_doctor.py` — wechat/bilibili 状态显示新逻辑
- `tests/test_cmd_sources.py` — wechat/bilibili 展示新 tier
- `tests/test_router.py` — wechat/bilibili 不在 quick mode 默认
- `README.md` — 支持的源表 + tier 注解更新, 「如何取全文」表加 wechat/bilibili 行的更新
- `CLAUDE.md` — v0.9.0-alpha 已发布版本条目 + v0.8 候选 mark done
- `pyproject.toml` — 0.8.1-alpha → 0.9.0-alpha; deps 加 `lxml`, `cssselect`
- `omnireach/__init__.py` — `__version__` 同步

**新增**:
- `omnireach/adapters/_wechat_sogou.py` — Sogou backend
- `omnireach/adapters/_bilibili_api.py` — B站 API backend
- `tests/adapters/fixtures/sogou_wechat_serp.html` — 真实 Sogou SERP 摘片做 fixture
- `tests/adapters/fixtures/bilibili_search_response.json` — 真实 B站 API JSON 摘片
- `tests/adapters/test__wechat_sogou.py` — Sogou backend 单元测试
- `tests/adapters/test__bilibili_api.py` — B站 backend 单元测试

## 5. 测试策略

### 5.1 单元（mock）
- Sogou backend: fixture HTML（真 SERP 摘片）→ 解析断言所有字段
- B站 backend: fixture JSON → 解析断言所有字段
- wechat orchestrator: monkeypatch 两个 backend，覆盖 4 个分支（有 Key 成功 / 有 Key 失败 fallback / 无 Key 走 Sogou / 两个都失败）
- bilibili orchestrator: 同上
- registry `enhanced_with` 字段
- doctor wechat 双后端逻辑
- router wechat/bilibili 不在 quick

### 5.2 真实 E2E（v0.8.1 教训：必须真跑）
- `uv run omnireach search --on wechat --json "claude 4.7"` — 验证无 Key 时 Sogou 真返结果 + content 截到 500
- `uv run omnireach search --on bilibili --json "claude 4.7"` — 验证 B站 API 真返 video block
- 用 `EXA_API_KEY=xxx` 还得测一次吗？—— 我没 Key，让用户在 PR review 时帮验证一次（在 PR description 写出来）。这是诚实的 E2E 缺口标记。

## 6. 版本号

`0.8.1-alpha` → `0.9.0-alpha`. minor bump：
- 公开行为变更：wechat/bilibili 无 Key 也能跑（之前 ❌）
- tier 变更
- 新 deps 加入 (lxml, cssselect)

## 7. 发版流程

按 CLAUDE.md「Release 流程」: feat 分支 → push → PR → squash merge → tag → `gh release create`.

## 8. 零变化项

- contract.py（v0.8 validator 保留，本次零改动）
- 其他 adapter（HN/youtube/github/rss/reddit/twitter/tiktok/douyin/xiaohongshu/exa/tavily/brave/perplexity/web）
- preferences.toml schema
- Skill manifest
