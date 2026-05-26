# omnireach v0.8.0-alpha — SERP snippet 截断架构修复

Date: 2026-05-27
Status: approved
Version target: `v0.8.0-alpha`

## 1. 背景

v0.1 ~ v0.7 期间，4 个长文本源 adapter 把上游全文塞进 `SearchResult.content` 字段：

| Adapter | 当前 `content` 来源 | 典型长度 |
|---|---|---|
| `wechat` | `hit["text"]` (Exa 全文) | 数千 ~ 数万字 |
| `xiaohongshu` | `item["content"]` (OpenCLI) | 数百 ~ 数千字 |
| `exa` | `hit["text"]` | 数千 ~ 数万字 |
| `tavily` | `hit["content"]` | 数百 ~ 数千字 |

这违反 CLAUDE.md「架构边界 — 三层架构」节锁死的 SERP-only 规则。omnireach 的职责是 search 层（返 metadata + URL），全文留给未来 sister repo `omnifetch`。

## 2. 关键洞察 — 无信息丢失

4 个违规 adapter **早已**把整个上游 payload 存进 `SearchResult.raw`：

```python
# omnireach/adapters/wechat.py:53
SearchResult(..., content=hit.get("text") or "", raw=hit)
```

`raw` 是 `dict[str, Any]`，承载上游原始字段。截断 `content` 不会丢任何东西 —— Agent 想要全文直接 `result.raw["text"]` / `result.raw["content"]`。

这消解了「违反三层架构 vs 信息丢失」的紧张关系。CLAUDE.md 此前把 omnifetch 写进 fix 路径有误导嫌疑（暗示要重新 fetch），真实情况是 raw 已经背着全文。omnifetch 未来的真正用武之地是 omnireach **本来就没有全文**的场景：HN 评论线、GH issue 完整 thread、Twitter 长 thread 展开等。

## 3. 设计决策

### 3.1 截断逻辑放在 contract 层（pydantic validator）

在 `omnireach/contract.py` 的 `SearchResult` 模型加 `field_validator("content")`：

```python
_SNIPPET_MAX = 500
_ELLIPSIS = "…"

@field_validator("content")
@classmethod
def _truncate_content(cls, v: str) -> str:
    if len(v) <= _SNIPPET_MAX:
        return v
    return v[:_SNIPPET_MAX] + _ELLIPSIS
```

**Why contract 层而不是各 adapter 内**：
- 架构边界由契约强制，不靠 adapter 作者自觉
- 未来任何新 adapter 自动合规
- reddit selftext / GH issue body 等当前未爆但同样违反 SERP-only 的源一并治理
- 单一实现点，单一测试点

### 3.2 截断策略：500 字符 + "…"

- 阈值 `_SNIPPET_MAX = 500`（来自 CLAUDE.md「~500 字 snippet」）
- 超长则取前 500 字符并追加 U+2026 省略号
- 阈值是字符数 `len(v)`，CJK 友好（一个汉字 = 一个 char）
- 不做 sentence-boundary smart trim（YAGNI；Agent 消费者不关心断句美观）
- 已含 `…` 的输入不去重 / 不识别（pure post-processing；上游就带 ellipsis 的话原样附加一个 trailing ellipsis 是可接受的边角行为，不值得加复杂度）

### 3.3 全文保留路径不变

`raw` 字段不动。4 个 adapter 不改一行。Agent 取全文：

```python
result.content              # 500 字 snippet + "…"
result.raw["text"]          # Exa / wechat 全文
result.raw["content"]       # Tavily / xhs 全文
```

### 3.4 不做的事（YAGNI）

- 不加 `truncated: bool` 字段（"…" 后缀已是宇宙通用截断信号；未来 omnifetch ship 时再补 pydantic 加字段是向后兼容操作）
- 不加 `full_content: str | None` 字段（`raw` 已有）
- 不加 `_SNIPPET_MAX` 的 `preferences.toml` 配置项（无人喊；500 是合理默认）
- 不做 sentence-boundary smart trim
- 不开 `omnifetch` 仓库（架构边界依然成立，留给真有 issue 时再开）
- 不动 4 个违规 adapter 的源代码（contract 层修复，adapter 零改动）

## 4. 范围与文件清单

### 4.1 改动文件

| 文件 | 改动 |
|---|---|
| `omnireach/contract.py` | 加 `_SNIPPET_MAX` / `_ELLIPSIS` 常量；`SearchResult` 加 `_truncate_content` validator |
| `tests/test_contract.py` | 加 5 个 validator 用例 |
| `tests/adapters/test_wechat.py` | mock fixture content 加长至 >500 字，断言截断 + raw 保留全文 |
| `tests/adapters/test_xiaohongshu.py` | 同上 |
| `tests/adapters/test_exa.py` | 同上 |
| `tests/adapters/test_tavily.py` | 同上 |
| `README.md` | 新增「如何取全文」小节 |
| `CLAUDE.md` | 「永远不做的事」第 4 条加补充；「当前违规」段标记已修；「v0.8 候选」中此项标 done |
| `pyproject.toml` | version `0.7.2-alpha` → `0.8.0-alpha` |
| `omnireach/__init__.py` | `__version__` 同步 |

### 4.2 测试用例细节

**`tests/test_contract.py` 新增**：
1. content ≤ 500 字符 → 原样返回（边界用 499 字）
2. content == 500 字符 → 原样返回（精确边界）
3. content == 501 字符 → 截到 500 + "…"
4. content 空串 → 原样返回空串
5. content 含 CJK（如「微信公众号」一类）→ 按字符截，不按字节

**4 个 adapter 测试新增**：每个文件加一个「long content gets truncated, raw preserved」用例：
- 构造 mock upstream response，content/text 字段塞 1000+ 字
- 调用 adapter.search()
- 断言 `result.content` 长度 == 501（500 + "…"）且以 "…" 结尾
- 断言 `result.raw["text"]` / `result.raw["content"]` 仍是完整 1000+ 字

预计测试总数：209 → 约 218（+9）。

## 5. 版本号决定

`0.7.2-alpha` → `0.8.0-alpha`。

minor bump 理由：`content` 字段输出形状变了 —— 之前给全文，现在给 snippet。算公开 API 行为变更，按 semver 在 0.x 阶段 minor 反映 behavior change 是合理的。无 patch-only 选项因为这不是 bug fix（是架构修正 + 输出 contract 变化）。

## 6. 发版流程

按 CLAUDE.md「Release 流程」执行：
1. 一条 feat commit on feat 分支
2. PR → squash merge to main
3. `git tag v0.8.0-alpha && git push --tags`
4. `gh release create v0.8.0-alpha --title "v0.8.0-alpha — SERP snippet truncation" --notes "..."`
5. 删 feat 分支

## 7. 验证

- `pytest` 全绿，218 ish 个测试
- `omnireach check-update` 提示有新版（自测）
- 不需要真 E2E：纯字符串后置处理，无上游交互；与之前 hotfix 不同（v0.7.1 是字段映射问题，必须真跑；这次是 contract 层 validator，pydantic 行为可单元化验证）

## 8. 不影响项

- dispatcher / normalizer / scorer / wizard / setup / doctor 全部零改动
- Skill manifest 零改动
- sources.yml 零改动
- 4 个 adapter 源码零改动（只改 contract 层 + 测试）
- preferences.toml schema 零改动
- 其他 13 个 adapter 行为不受可见影响（它们的 content 本来就 <500）
