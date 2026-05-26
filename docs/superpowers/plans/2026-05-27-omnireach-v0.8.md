# omnireach v0.8.0-alpha Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Spec: `docs/superpowers/specs/2026-05-27-omnireach-v0.8-design.md`.

**Goal:** Ship v0.8.0-alpha — enforce SERP-snippet rule at the `SearchResult` contract layer by truncating `content` to 500 chars + "…". Full upstream payloads remain accessible via `result.raw` (already preserved by the 4 violating adapters).

**Architecture:** Single pydantic `field_validator` on `SearchResult.content` in `omnireach/contract.py`. Zero changes to any adapter source. Adapter test fixtures get one new case each (long content → truncated content + full `raw`). Three documentation files synced (README "如何取全文" subsection, CLAUDE.md status flip, pyproject + `__init__.py` version bump).

**Tech Stack:** Python 3.11+, pydantic v2 (`field_validator`), pytest. No new deps.

---

## File Structure

**Modified:**
- `omnireach/contract.py` — add `_SNIPPET_MAX` / `_ELLIPSIS` module-level constants; add `_truncate_content` `field_validator` on `SearchResult.content`
- `tests/test_contract.py` — add 5 new validator cases
- `tests/adapters/test_wechat.py` — add one "long content gets truncated, raw preserved" case
- `tests/adapters/test_xiaohongshu.py` — same
- `tests/adapters/test_exa.py` — same
- `tests/adapters/test_tavily.py` — same
- `README.md` — add "## 如何取全文" subsection between 「💎 付费 booster」 and 「⚙️ 用户偏好」
- `CLAUDE.md` — flip 「当前违规」 status + amend 「永远不做的事」 #4 + mark v0.8 candidate done
- `pyproject.toml` — `version = "0.7.2-alpha"` → `version = "0.8.0-alpha"`
- `omnireach/__init__.py` — `__version__ = "0.7.2-alpha"` → `__version__ = "0.8.0-alpha"`

**Created:** none.

---

## Task 0: Create feat branch

**Files:** none (git only)

- [ ] **Step 1: Verify clean main**

Run: `git status && git log --oneline -1`
Expected: working tree clean, on `main`, HEAD at `bc0d105` (spec commit) or later.

- [ ] **Step 2: Create and checkout feat branch**

Run: `git checkout -b feat/v0.8-snippet-truncation`
Expected: `Switched to a new branch 'feat/v0.8-snippet-truncation'`

---

## Task 1: Add validator + 5 unit tests (TDD)

**Files:**
- Modify: `omnireach/contract.py`
- Modify: `tests/test_contract.py`

- [ ] **Step 1: Write the 5 failing tests**

Append to `tests/test_contract.py`:

```python
def test_content_short_unchanged():
    """Content <= 500 chars is returned as-is (lower boundary case at 499)."""
    short = "x" * 499
    r = SearchResult(
        source="hackernews", adapter="builtin", title="t", url="https://e.x/1",
        content=short,
    )
    assert r.content == short
    assert len(r.content) == 499


def test_content_exact_500_unchanged():
    """Content == 500 chars is on the boundary; not truncated."""
    exact = "x" * 500
    r = SearchResult(
        source="hackernews", adapter="builtin", title="t", url="https://e.x/1",
        content=exact,
    )
    assert r.content == exact
    assert len(r.content) == 500


def test_content_long_gets_truncated_with_ellipsis():
    """Content > 500 chars is truncated to first 500 chars + '…'."""
    long = "y" * 600
    r = SearchResult(
        source="exa", adapter="exa-api", title="t", url="https://e.x/1",
        content=long,
    )
    assert r.content == "y" * 500 + "…"
    assert len(r.content) == 501  # 500 chars + 1 ellipsis char
    assert r.content.endswith("…")


def test_content_empty_unchanged():
    """Empty content stays empty (no spurious ellipsis)."""
    r = SearchResult(
        source="hackernews", adapter="builtin", title="t", url="https://e.x/1",
        content="",
    )
    assert r.content == ""


def test_content_cjk_truncates_by_character_count():
    """CJK content truncates by character count, not byte count."""
    # 1000 汉字, each is 1 Python char but 3 UTF-8 bytes
    cjk = "微" * 1000
    r = SearchResult(
        source="wechat", adapter="exa-api", title="t", url="https://mp.weixin.qq.com/x",
        content=cjk,
    )
    assert r.content == "微" * 500 + "…"
    assert len(r.content) == 501  # by character count
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_contract.py -v -k "content_"`
Expected: 4 of 5 fail (the empty-content one happens to pass since "" is unchanged). Specifically:
- `test_content_short_unchanged` — PASS by accident (no validator yet, returns unchanged)
- `test_content_exact_500_unchanged` — PASS by accident
- `test_content_long_gets_truncated_with_ellipsis` — **FAIL** (no truncation)
- `test_content_empty_unchanged` — PASS by accident
- `test_content_cjk_truncates_by_character_count` — **FAIL** (no truncation)

The two FAIL cases are the meaningful coverage. The "PASS by accident" cases will become PASS-by-validator after Step 3.

- [ ] **Step 3: Implement the validator in `omnireach/contract.py`**

Replace the current `omnireach/contract.py` with:

```python
"""SearchResult JSON contract — the boundary between omnireach core and adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# v0.8: SERP-snippet rule enforced at the contract boundary. Full upstream
# payloads remain accessible via SearchResult.raw — see
# docs/superpowers/specs/2026-05-27-omnireach-v0.8-design.md.
_SNIPPET_MAX = 500
_ELLIPSIS = "…"


class Engagement(BaseModel):
    model_config = ConfigDict(extra="allow")
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    views: int | None = None


class SearchResult(BaseModel):
    """One normalized hit from one source."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="logical source id, e.g. 'hackernews'")
    adapter: str = Field(description="which adapter produced this, e.g. 'agent-reach'")
    title: str
    url: str
    content: str = ""
    author: str | None = None
    ts: str | None = Field(default=None, description="ISO 8601 publish ts")
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    engagement: Engagement | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    cost: Literal["free", "paid"] = "free"
    raw_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("content")
    @classmethod
    def _truncate_content(cls, v: str) -> str:
        if len(v) <= _SNIPPET_MAX:
            return v
        return v[:_SNIPPET_MAX] + _ELLIPSIS


class SourceError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    error: str
    category: Literal["unavailable", "failed"] = "failed"


class SearchEnvelope(BaseModel):
    """The top-level JSON returned by `omnireach "<query>"`."""

    model_config = ConfigDict(extra="forbid")

    query: str
    ts: str
    results: list[SearchResult] = Field(default_factory=list)
    errors: list[SourceError] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_contract.py -v`
Expected: all `test_content_*` cases PASS; the pre-existing 4 tests in `test_contract.py` also PASS (validator is backwards-compatible for content <= 500 chars).

- [ ] **Step 5: Commit**

```bash
git add omnireach/contract.py tests/test_contract.py
git commit -m "feat(contract): truncate SearchResult.content to 500-char SERP snippet"
```

---

## Task 2: Extend the 4 adapter tests with long-content fixture

**Files:**
- Modify: `tests/adapters/test_wechat.py`
- Modify: `tests/adapters/test_xiaohongshu.py`
- Modify: `tests/adapters/test_exa.py`
- Modify: `tests/adapters/test_tavily.py`

Each test gets one new case asserting (a) `content` is truncated to 501 chars (500 + ellipsis) and (b) `raw["text"]` / `raw["content"]` keeps the full original. All four are independent — no shared fixture needed.

- [ ] **Step 1: Write the failing test for wechat**

Append to `tests/adapters/test_wechat.py`:

```python
def test_search_truncates_content_but_preserves_full_in_raw(monkeypatch):
    """v0.8: contract validator truncates content to 500 + '…'; raw['text'] keeps full."""
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    long_text = "啊" * 1200
    payload = {"results": [
        {"title": "长文公众号", "url": "https://mp.weixin.qq.com/s/long",
         "publishedDate": "2026-05-22T10:00:00Z", "text": long_text}
    ]}
    real_client = httpx.AsyncClient(transport=_mock_transport(200, payload))
    with patch("omnireach.adapters.wechat.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(WeChatAdapter().search("q", limit=5))
    assert len(out) == 1
    assert out[0].content == "啊" * 500 + "…"
    assert len(out[0].content) == 501
    assert out[0].raw["text"] == long_text
    assert len(out[0].raw["text"]) == 1200
```

- [ ] **Step 2: Run the wechat test to verify it passes**

Run: `pytest tests/adapters/test_wechat.py::test_search_truncates_content_but_preserves_full_in_raw -v`
Expected: PASS (validator from Task 1 is already in place).

Note: this case is technically a regression assertion, not strict TDD, since the validator already exists by this task. The point of writing it is to document the cross-layer behavior at the adapter level.

- [ ] **Step 3: Write and run the xiaohongshu test**

Append to `tests/adapters/test_xiaohongshu.py`:

```python
async def test_xhs_truncates_content_but_preserves_full_in_raw(monkeypatch):
    """v0.8: long xhs post body gets truncated in content, full kept in raw."""
    long_body = "种" * 1500
    fake = json.dumps([
        {
            "title": "长种草笔记",
            "url": "https://xiaohongshu.com/discovery/item/long",
            "author": "AI小白",
            "content": long_body,
            "published_at": "2026-05-21T08:00:00Z",
            "like_count": 1,
            "comment_count": 0,
            "collect_count": 0,
        }
    ])

    async def fake_exec(*args, **kwargs):
        class P:
            returncode = 0

            async def communicate(self):
                return (fake.encode(), b"")

        return P()

    monkeypatch.setattr("omnireach.adapters.xiaohongshu.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("omnireach.adapters.xiaohongshu.shutil.which", lambda n: "/usr/bin/" + n)

    out = await XiaohongshuAdapter().search("q")
    assert len(out) == 1
    assert out[0].content == "种" * 500 + "…"
    assert len(out[0].content) == 501
    assert out[0].raw["content"] == long_body
    assert len(out[0].raw["content"]) == 1500
```

Run: `pytest tests/adapters/test_xiaohongshu.py::test_xhs_truncates_content_but_preserves_full_in_raw -v`
Expected: PASS.

- [ ] **Step 4: Write and run the exa test**

Append to `tests/adapters/test_exa.py`:

```python
def test_search_truncates_content_but_preserves_full_in_raw(monkeypatch):
    """v0.8: long Exa text gets truncated in content, full kept in raw['text']."""
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    long_text = "a" * 1024
    payload = {"results": [
        {"title": "Long article", "url": "https://e/long",
         "text": long_text, "author": "n"}
    ]}
    real_client = httpx.AsyncClient(transport=_mock_transport(200, payload))
    with patch("omnireach.adapters.exa.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(ExaAdapter().search("q", limit=5))
    assert len(out) == 1
    assert out[0].content == "a" * 500 + "…"
    assert len(out[0].content) == 501
    assert out[0].raw["text"] == long_text
    assert len(out[0].raw["text"]) == 1024
```

Run: `pytest tests/adapters/test_exa.py::test_search_truncates_content_but_preserves_full_in_raw -v`
Expected: PASS.

- [ ] **Step 5: Write and run the tavily test**

Append to `tests/adapters/test_tavily.py`:

```python
def test_search_truncates_content_but_preserves_full_in_raw(monkeypatch):
    """v0.8: long Tavily content gets truncated, full kept in raw['content']."""
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")
    long_text = "b" * 900
    payload = {"results": [
        {"title": "Long", "url": "https://e/long",
         "content": long_text, "published_date": "2026-05-20T10:00:00Z"}
    ]}
    real_client = httpx.AsyncClient(transport=_mock_transport(200, payload))
    with patch("omnireach.adapters.tavily.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = real_client
        out = asyncio.run(TavilyAdapter().search("q", limit=5))
    assert len(out) == 1
    assert out[0].content == "b" * 500 + "…"
    assert len(out[0].content) == 501
    assert out[0].raw["content"] == long_text
    assert len(out[0].raw["content"]) == 900
```

Run: `pytest tests/adapters/test_tavily.py::test_search_truncates_content_but_preserves_full_in_raw -v`
Expected: PASS.

- [ ] **Step 6: Run full adapter test suite to make sure nothing else broke**

Run: `pytest tests/adapters/ -v`
Expected: all green. Especially confirm `test_search_returns_results_with_cost_paid` (exa + tavily) and `test_search_sends_include_domains` (wechat) still pass — these existing tests use short content like "snippet" / "正文" which is well under 500 so the validator is a no-op for them.

- [ ] **Step 7: Commit**

```bash
git add tests/adapters/test_wechat.py tests/adapters/test_xiaohongshu.py tests/adapters/test_exa.py tests/adapters/test_tavily.py
git commit -m "test(adapters): assert v0.8 content truncation + raw full-text preservation"
```

---

## Task 3: Version bump

**Files:**
- Modify: `pyproject.toml`
- Modify: `omnireach/__init__.py`

- [ ] **Step 1: Bump version in pyproject.toml**

In `pyproject.toml`, change:
```toml
version = "0.7.2-alpha"
```
to:
```toml
version = "0.8.0-alpha"
```

- [ ] **Step 2: Bump version in `omnireach/__init__.py`**

In `omnireach/__init__.py`, change:
```python
__version__ = "0.7.2-alpha"
```
to:
```python
__version__ = "0.8.0-alpha"
```

- [ ] **Step 3: Verify versions stay in sync**

Run: `grep -E '^version|^__version__' pyproject.toml omnireach/__init__.py`
Expected: both show `0.8.0-alpha`.

- [ ] **Step 4: Run full test suite as a regression sweep**

Run: `pytest -q`
Expected: all green. Test count should be ~218 (209 previous + 5 contract + 4 adapter = 218).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml omnireach/__init__.py
git commit -m "chore: bump version to 0.8.0-alpha"
```

---

## Task 4: README "如何取全文" subsection

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Insert new subsection between 「💎 付费 booster」 and 「⚙️ 用户偏好」**

In `README.md`, find the closing of the booster section:

```
要禁用：编辑 `~/.omnireach/preferences.toml` 设 `[boosters] auto_enable = false`。

## ⚙️ 用户偏好 (v0.4)
```

Insert the following new section between those two paragraphs (after the `要禁用：` line, before `## ⚙️ 用户偏好`):

```markdown

## 📄 如何取全文 (v0.8)

omnireach 是 search 层, `content` 字段始终是 SERP snippet (≤ 500 字 + `…`)。这是有意为之 —— 全文留给未来 `omnifetch` 层处理 (见上方 [关于命名](#关于命名-omnireach-是工具集-suite-不是单一工具))。

但对于 wechat / xiaohongshu / exa / tavily 这 4 个上游本身就返全文的源, **完整原始 payload 保留在 `result.raw` 字典里**, Agent 想要全文时直接取:

```python
# Python (调用方)
from omnireach.api import search   # 假设你以库方式集成
env = await search("query", on=["wechat"])
snippet = env.results[0].content        # 500 字 + "…"
full    = env.results[0].raw["text"]    # Exa/wechat 全文
# xiaohongshu / tavily 对应 raw["content"]
```

```bash
# CLI + jq
omnireach search --json --on tavily "claude 4.7" | \
  jq '.results[] | {title, snippet: .content, full: .raw.content}'
```

字段对应表:

| 源 | `result.content` | `result.raw[...]` 取全文 |
|---|---|---|
| wechat | snippet | `raw["text"]` |
| exa | snippet | `raw["text"]` |
| xiaohongshu | snippet | `raw["content"]` |
| tavily | snippet | `raw["content"]` |

其他源 (HN / GitHub / RSS / YouTube / 等) 的 content 本身就 < 500 字, 不会被截断, 也不需要 raw 兜底。

```

- [ ] **Step 2: Sanity-check the rendered markdown**

Run: `grep -n "如何取全文\|⚙️ 用户偏好" README.md`
Expected: the new "📄 如何取全文 (v0.8)" header appears before "⚙️ 用户偏好 (v0.4)".

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): add v0.8 \"如何取全文\" section pointing at result.raw"
```

---

## Task 5: CLAUDE.md status updates

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update 「永远不做的事」 #4**

In `CLAUDE.md`, find:
```
- 长文本源 (wechat / xhs / exa / tavily) content 字段应截到 ~500 字 snippet, 全文留给 omnifetch
```

Replace with:
```
- 长文本源 (wechat / xhs / exa / tavily) content 字段应截到 ~500 字 snippet (v0.8 起由 `SearchResult` validator 强制), 全文保留在 `result.raw` 中, Agent 按需取用; 真要 omnifetch 才能拿的是 omnireach 本来就没全文的场景 (HN/GH/Twitter thread 等)
```

- [ ] **Step 2: Update 「当前违规」 段**

In `CLAUDE.md`, find:
```
**当前违规** (v0.7.2 现状, v0.8 要 fix): wechat / xiaohongshu / exa / tavily 4 个 adapter 的 `content` 字段塞了**整篇全文**, 不是 SERP snippet。v0.8 用粗暴截断 (不跑 LLM) 修这个。
```

Replace with:
```
**~~当前违规~~已修** (v0.8 修复): 4 个长文本源 (wechat/xiaohongshu/exa/tavily) 在 `SearchResult.content` 上的全文塞入由 contract 层 `field_validator` 截到 500 字 + "…"; 全文保留在 `result.raw` 中。见 `docs/superpowers/specs/2026-05-27-omnireach-v0.8-design.md`。
```

- [ ] **Step 3: Mark v0.8 candidate as done**

In `CLAUDE.md`, find the v0.8 候选 list:
```
- 4 个长文本源 content 字段截断到 ~500 字 snippet (修架构违规, 见上方边界决策)
```

Replace with:
```
- ~~4 个长文本源 content 字段截断到 ~500 字 snippet~~ ✅ done in v0.8.0-alpha
```

- [ ] **Step 4: Add v0.8.0-alpha entry to 「已发布版本」 (predates final tag, hence WIP — will become final on Task 7)**

In `CLAUDE.md`, in the 「已发布版本」 list (currently ends at `v0.7.2-alpha`), append:
```
- `v0.8.0-alpha` (2026-05-27): **架构修复** — `SearchResult.content` 在 contract 层 (pydantic `field_validator`) 强制截到 500 字 + "…"; 全文保留在 `result.raw` (4 个长文本源 wechat/xhs/exa/tavily 上游 payload 本就存了)。零 adapter 改动, 单一实现点防未来 adapter 漂移。218 tests。PR #__TBD__
```

(The `#__TBD__` placeholder gets filled in at Task 7 once PR number is known.)

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude.md): mark v0.8 SERP-snippet fix as done; flip status sections"
```

---

## Task 6: Push branch and open PR

**Files:** none (git + gh only)

- [ ] **Step 1: Push the feat branch**

Run: `git push -u origin feat/v0.8-snippet-truncation`
Expected: branch pushed, PR URL hint printed.

- [ ] **Step 2: Open PR**

Run:
```bash
gh pr create --title "feat: v0.8.0-alpha — SERP snippet truncation at contract layer" --body "$(cat <<'EOF'
## Summary

- Adds `field_validator` on `SearchResult.content` in `omnireach/contract.py` that truncates content to 500 chars + "…"
- Zero changes to any adapter source — 4 violating adapters (wechat/xhs/exa/tavily) already preserve full upstream payload in `result.raw`
- Documents the "how to get full text" path via `result.raw["text"]` / `result.raw["content"]` in README
- Bumps version to `0.8.0-alpha` (minor: behavior change on the `content` output contract)

Spec: `docs/superpowers/specs/2026-05-27-omnireach-v0.8-design.md`
Plan: `docs/superpowers/plans/2026-05-27-omnireach-v0.8.md`

## Test plan

- [x] `pytest -q` passes (~218 tests, +9 from v0.7.2)
- [x] 5 new validator unit tests in `tests/test_contract.py`
- [x] 4 new adapter-level assertions confirming `content` truncates but `raw[...]` keeps full text
- [x] Existing tests stay green (short-content adapters unaffected, validator is no-op for ≤500 chars)

No real E2E this time — change is a pure post-processing pydantic validator with no upstream interaction.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
Expected: PR URL printed (note the number, fill into CLAUDE.md placeholder).

- [ ] **Step 3: Fill the PR number into CLAUDE.md**

In `CLAUDE.md`, find `PR #__TBD__` and replace with the actual PR number (e.g. `PR #18`).

Commit and push:
```bash
git add CLAUDE.md
git commit -m "docs(claude.md): fill v0.8 PR number"
git push
```

---

## Task 7: Merge, tag, release

**Files:** none (git + gh only)

- [ ] **Step 1: Wait for CI / self-review to clear, then squash-merge**

Run: `gh pr merge --squash --delete-branch`
Expected: PR merged into main; remote feat branch deleted.

- [ ] **Step 2: Sync local main and verify the squash-merge landed**

Run: `git checkout main && git pull && git log --oneline -3`
Expected: top commit is the v0.8 squash from the merged PR.

- [ ] **Step 3: Tag and push**

Run:
```bash
git tag v0.8.0-alpha && git push --tags
```
Expected: tag pushed.

- [ ] **Step 4: Create GitHub release**

Run:
```bash
gh release create v0.8.0-alpha --title "v0.8.0-alpha — SERP snippet truncation" --notes "$(cat <<'EOF'
## SERP-snippet rule enforced at the contract layer

`SearchResult.content` now truncates to 500 characters + "…" via a pydantic `field_validator` in `omnireach/contract.py`. This fixes the architecture violation tracked since v0.1 where 4 long-text adapters (wechat / xiaohongshu / exa / tavily) stuffed full article text into the search-result content field, blowing token budgets and blurring the three-layer architecture (search vs fetch vs parse).

## No information loss

All 4 affected adapters were already saving the full upstream payload to `result.raw`. To get full text in any caller:

```python
snippet = result.content      # 500 chars + "…"
full    = result.raw["text"]      # Exa / wechat
full    = result.raw["content"]   # Tavily / xhs
```

See [README "如何取全文"](https://github.com/Daily-AC/omnireach#-如何取全文-v08) for the full field-mapping table.

## Why not LLM-summarized snippets?

Because omnireach's users are Agents (which are themselves LLMs). They can consume raw truncated text just fine — no need for omnireach to introduce a sub-LLM Haiku dependency the way Claude Code's WebSearch does for human consumption.

## Changes

- `omnireach/contract.py` — `_SNIPPET_MAX = 500` constant + `_truncate_content` validator on `SearchResult.content`
- Zero changes to any adapter source code
- 5 new contract tests + 4 new adapter assertions = 218 tests total
- README + CLAUDE.md updated

## Upgrade

```bash
omnireach check-update
uv tool upgrade omnireach
```

**Compatibility note:** if you previously relied on `result.content` carrying full article text for the 4 long-text sources, switch to `result.raw["text"]` / `result.raw["content"]`. No other consumer changes needed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
Expected: release created and marked Latest.

- [ ] **Step 5: Verify release is Latest and check-update works**

Run:
```bash
gh release view v0.8.0-alpha --json isLatest,tagName
omnireach check-update
```
Expected: `isLatest=true`; `check-update` no longer says "up to date" (since the installed version is still 0.7.2 unless re-installed) or says "you have 0.8.0-alpha" if user re-installed locally — either is acceptable since this verifies the API roundtrip.

If `isLatest` is `false`, run: `gh release edit v0.8.0-alpha --latest`.

---

## Done criteria

- [ ] PR merged, feat branch deleted (remote + local)
- [ ] Tag `v0.8.0-alpha` pushed and visible at `https://github.com/Daily-AC/omnireach/releases`
- [ ] GitHub Release exists, marked `Latest`
- [ ] `omnireach check-update` reports the new version (sanity)
- [ ] `pytest -q` shows ~218 passing tests on main
- [ ] CLAUDE.md is consistent: 「当前违规」 segment marked done, v0.8 candidate struck through, v0.8.0-alpha entry exists in 已发布版本 with real PR number
