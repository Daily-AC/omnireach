# omnireach v0.10.1-alpha — OpenCLI wechat fetch + CAPTCHA detection 设计 spec

**Status**: draft, awaiting team-lead review
**Author**: wechat-reverser (subagent)
**Date**: 2026-05-27
**Decision gates**: team-lead 必须 approve 这份 spec 才能进 M2 (改 OpenCLI code)

---

## 1. 背景与触发

今天 (2026-05-27) v0.10.0-alpha ship 后, 用户拿 `omnireach fetch <mp.weixin.qq.com/s/...>` 测真实公众号文章, **crwl + jina 两个 backend 都被微信"环境异常"验证码拦住**, 返了垃圾 markdown 且 silent 不报错。

根因:

1. WeChat 公众号反爬强 (前端 `navigator.webdriver` 检测 + 后端 referer/cookie/IP 风控)
2. crwl / jina 都不带登录态, 拿到的是 `https://weixin.sogou.com/antispider/...` 风格的验证页
3. omnireach 的 search 侧 4 个登录态源 (twitter / xhs / tiktok / douyin) 走 OpenCLI 登录态 Chrome 通道, **但 WeChat 没接到这条 OpenCLI 通道**

WeChat 是 omnireach 目前唯一一个**真正没有 fetch 通道**的 host。

## 2. 现状调研 — OpenCLI 已经把活儿干完了

clone `Daily-AC/OpenCLI` 一看, **`clis/weixin/` 早就存在且功能完整**:

| 文件 | 来源 | 功能 |
|---|---|---|
| `clis/weixin/search.js` | upstream PR #1250 (Carson, 2026-05-06, tag v1.7.13) | Sogou 微信搜索, 自带 CAPTCHA 检测 (`/验证码\|安全验证\|异常访问/`), 走 `weixin.sogou.com` |
| `clis/weixin/download.js` | upstream PR #1042 (more recent revisions) | `mp.weixin.qq.com/s/xxx` → Markdown 文件, 自带反爬检测 `detectWechatAccessIssue()`, Strategy.COOKIE (登录态 Chrome), 输出到 `--output ./weixin-articles` 目录, 顺手 dl 图片 |
| `clis/weixin/drafts.js`, `create-draft.js` | upstream #1095 | 公众号草稿 write 命令 (我们不用) |

**Fork 跟 jackwener upstream main 在 `clis/weixin/` 上 0 字节差异** (`git diff FETCH_HEAD HEAD -- clis/weixin/` 返空)。

这意味着原任务"在 fork 加 wechat module 仿 douyin 模式" — **前提错了**。OpenCLI 这边的 module 工作完全不需要做。

## 3. 真 gap — download 写文件, omnireach fetch 要 stdout

`weixin/download.js` 当前形态是**把 markdown 写到 `--output` 目录的 .md 文件**, 返一行 `{title, author, publish_time, status, size, saved}` 行级元数据。

但 omnireach `fetch <url>` 的契约 (跟 crwl / jina 一致) 是: **stdout 直接吐 markdown 全文**, Agent 一管道直接拿。让 omnireach 调 `opencli weixin download` 然后 glob tmpdir 里的 .md 文件 — 别扭。

## 4. 决策 — 选 B (`--stdout` flag), 拒 A 和 C

### 选项 A: omnireach 读 OpenCLI 写的文件

`fetch.py` 调 `opencli weixin download --url <url> --output <tmpdir>`, 然后 glob tmpdir 里的 .md, 读出来吐 stdout, 清理 tmpdir。

- **优点**: 零上游改动, 立刻可用
- **缺点**: tmpdir 生命周期管理 / glob `*.md` 假设 (downloadArticle 用 sanitizeFilename 生成的目录名 omnireach 这边不易预测) / 多次 IO / 失败路径清理 / Windows 临时文件锁问题
- **拒绝理由**: 为了省 ~30 行 JS 引入这么多 churn 不值

### 选项 B (✅ 选): 给 OpenCLI 加 `weixin download --stdout` flag

直接在 OpenCLI Daily-AC fork main 加 `--stdout` flag, mirror upstream **已经在 `clis/web/read` 上落地的同款模式** (见 §5)。

- **优点**:
  - 长期正确, OpenCLI 任何下游受益
  - 跟 `web/read.js` 一致 (一致性 = 维护性)
  - **改动极小**: 实际是 **3 行 JS** (manifest arg + 1 行 wiring + 1 行 swallow-rows)
  - 跟 OpenCLI 现有 `downloadArticle()` 共享 helper 完全兼容 — helper **已经有 `stdout?: boolean` option 了** (见 §5)
- **缺点**: 等上游 merge 周期; 但参考 douyin PR #1759 模式 — fork main 直接 push, omnireach 这边走 fork 不等上游

**Bonus 跟 OpenCLI 共享基础设施一致**: `src/download/article-download.ts` 的 `ArticleDownloadOptions` 接口里 `stdout?: boolean` **早已存在** (line 63), 实现路径 (line 388-398) 也都搭好了, `clis/web/read.js` 走的就是这条路。Carson / jackwener 设计 article-download.ts 时就预想了多 adapter 共用 stdout 模式。weixin 这边只是没把 flag 暴露到 CLI 层。

### 选项 C: 用 search 而非 download 取内容

WeChat search 当前 schema: `{rank, page, title, url, summary, publish_time}` — 只有 summary 没正文。

- **拒绝理由**: 不可行, 物理上拿不到全文

## 5. OpenCLI `--stdout` flag schema 设计

照搬 `clis/web/read.js:411` (现有 manifest arg):

```jsonc
// 在 weixin/download cli({...args:[...]}) 的 args 数组末尾追加
{ name: 'stdout', type: 'boolean', default: false,
  help: 'Print markdown to stdout instead of saving to a file' }
```

照搬 `clis/web/read.js:468` (现有 wiring):

```js
const result = await downloadArticle({...}, {
    output: kwargs.output,
    downloadImages: kwargs['download-images'],
    imageHeaders: { Referer: 'https://mp.weixin.qq.com/' },
    frontmatterLabels: { author: '公众号' },
    detectImageExt: (url) => { ... },
    stdout: kwargs.stdout,  // ← 新增
});
```

照搬 `clis/web/read.js:480` (现有 swallow-rows 模式):

```js
// `--stdout` is a content-streaming mode. The markdown body already went
// to process.stdout inside downloadArticle(), so returning rows here
// would make Commander append table/JSON output to the same stdout
// stream and break piping.
return kwargs.stdout ? null : result;
```

**file-output 互斥关系**: `stdout=true` 时, `downloadArticle()` 内部 (line 367 / line 388) 跳过 image download + mkdir + 文件写盘, 直接 `process.stdout.write(fullContent)` 然后返一行 `status: 'success'` 的 row (我们在 cli `func` 末尾 `return null` swallow 掉, 让 Commander 不再追加 JSON/table 到同一个 stdout 流)。**这部分是 `downloadArticle` 已经实现好的, 我们不动。**

**`stdout=true` + errorHint 冲突语义 lock** (M2 单元测试必须锁定):

- `download.js` 的 errorHint 早返路径在 line 294-303, **早于** `downloadArticle()` 调用 — `data?.errorHint === 'environment verification required'` 时直接 `return [{...}]`, `stdout` flag **不进**这个分支, 也**不影响**这个分支。
- errorHint 路径的 exit code 由 Commander runtime 控制: OpenCLI 整体 convention 是**把 "上游要验证" 当 row-level status, 不当 binary error**, 所以 exit code = 0。stdout 是 Commander `--format json` 序列化的 JSON row, body 形如 `[{"title": "Error", ..., "status": "failed — verification required in WeChat browser page", ...}]`。
- omnireach 这边按 §7.1 的 retcode + try-parse 双重逻辑识别: retcode=0 + stdout parses as JSON row with `status` 字段 + status 含 "verification" → `captcha_suspected`。
- **不**改 OpenCLI 让 errorHint 时 exit != 0 — 这跟 OpenCLI 整体 convention 不一致 (it 走 row-level status), 不该为我们一个下游下游违反 convention。
- 成功路径下: stdout 是纯 markdown body, parser fail-over 到 branch 3 (plain markdown 路径), 真文章正文哪怕以 `[作者按]` 起开头也不会被误判 — 因为 JSON parse 会失败, 或 parse 成功但不含 `status` 字段。

## 6. v0.10.1 scope 收窄

**只动 fetch 这条线, search 侧 wechat 不动**:

- 当前 `omnireach/adapters/wechat.py` 的 Exa > Sogou-httpx 路径用户没抱怨, 实测能用
- 引 OpenCLI `weixin search` 作第三候选是好事, **留给 v0.11**
- v0.10.1 聚焦解决今天 session 暴露的真痛点 (fetch 文章正文返垃圾验证页), 不顺手扩大 scope 让 ship 拖

用户上一轮 "search 多一条路径择优" 的指示推迟到 v0.11 落地, **不是放弃**, 是顺序。

## 7. omnireach 侧改动清单

### 7.1 `omnireach/commands/fetch.py` — host-aware routing

当前 fetch.py 的 backend 选择: `crwl` (default) → `jina` (fallback) → `auto` 二者择优。

新增 host-aware 短路:

```python
# 在 fetch_url() 进入 backend 分支前
WECHAT_HOSTS = {"mp.weixin.qq.com"}

def _host_of(url: str) -> str:
    return urlparse(url).hostname or ""

# 在选 backend 前
if _host_of(url) in WECHAT_HOSTS:
    # 强制走 OpenCLI, 忽略 --backend (除非 --backend 显式指定非 wechat backend)
    return _fetch_via_opencli_weixin(url)
```

`_fetch_via_opencli_weixin(url)` 实现 (改进版 — retcode + try-parse 双重判定, 不再用 `startswith("[")` 单字符启发):

```python
def _fetch_via_opencli_weixin(url: str) -> FetchResult:
    """Invoke `opencli weixin download --url <url> --stdout --format json`.

    Output disambiguation (3 branches):
      1. retcode != 0  → opencli_failed (binary-level error, stderr surfaced)
      2. retcode == 0 + stdout parses as JSON with a 'status' field
         → errorHint / row-level status path; check 'verification' keyword to
           split captcha_suspected vs opencli_failed
      3. retcode == 0 + stdout is NOT valid JSON (or has no 'status') → real
         markdown body (which could legitimately start with '[作者按]' etc.)
    """
    if not shutil.which("opencli"):
        return FetchResult(
            url=url, markdown="", errors=[FetchError(
                code="backend_unavailable",
                detail="OpenCLI not on PATH; install via npm i -g github:Daily-AC/OpenCLI",
            )],
        )
    proc = subprocess.run(
        ["opencli", "weixin", "download", "--url", url, "--stdout", "--format", "json"],
        capture_output=True, text=True, timeout=60,
    )
    # Branch 1: binary-level failure
    if proc.returncode != 0:
        return FetchResult(url=url, markdown="", errors=[FetchError(
            code="opencli_failed",
            detail=proc.stderr.strip() or f"non-zero exit ({proc.returncode})",
        )])
    out = proc.stdout
    # Branch 2: try-parse as JSON row (errorHint or row-level status)
    row = None
    try:
        parsed = json.loads(out.strip())
        candidate = parsed[0] if isinstance(parsed, list) and parsed else parsed
        if isinstance(candidate, dict) and "status" in candidate:
            row = candidate
    except (json.JSONDecodeError, ValueError):
        row = None
    if row is not None:
        status = str(row.get("status", ""))
        if "verification" in status.lower() or "环境异常" in status:
            return FetchResult(url=url, markdown="", errors=[FetchError(
                code="captcha_suspected", detail=status,
            )])
        # Any other row-level status with retcode=0 is an OpenCLI-layer "soft" failure
        return FetchResult(url=url, markdown="", errors=[FetchError(
            code="opencli_failed", detail=status,
        )])
    # Branch 3: plain markdown body (success)
    return FetchResult(url=url, markdown=out, errors=[])
```

**关于 `commands/fetch.py` 的 click `--backend` choices 改动**: 当前 v0.10.0 的 `--backend` choices 是 `["auto", "crwl", "jina"]`, M3 必须扩成 `click.Choice(["auto", "crwl", "jina", "opencli"])` — 让用户能显式 `--backend opencli` 触发本节描述的路径, 不只是 host-aware auto 触发。配合 §11 Q2 ack 的 "explicit user flag 赢" 语义: 用户显式 `--backend crwl` 在 mp.weixin.qq.com URL 上走 crwl + CAPTCHA 兜底; 默认 `auto` 时 mp.weixin.qq.com 短路到 opencli。

### 7.2 CAPTCHA 启发式 (兜底, 给 crwl/jina 用)

OpenCLI 路径走 errorHint, 比 grep 可靠 — 但 crwl/jina 拿到验证页时它们 silent 返垃圾 markdown。给这两个 backend 加个 post-hoc 启发式检测:

```python
CAPTCHA_KEYWORDS = (
    "环境异常",
    "完成验证后即可继续访问",
    "请输入验证码",
    "请完成安全验证",
    "Cloudflare",
    "Just a moment",
    "Checking your browser",
)

def _looks_like_captcha(markdown: str) -> tuple[bool, str | None]:
    if len(markdown) < 200:  # short response is suspicious for "real article" use case
        return False, None
    for kw in CAPTCHA_KEYWORDS:
        if kw in markdown:
            return True, kw
    return False, None
```

在 crwl/jina backend 返回后, 检测命中 → 往 errors 加 `captcha_suspected` entry。**这是 v0.10.0 silent failure 的真根因**, 必须修。

### 7.3 doctor 新加段

`commands/doctor.py` 当前有 `fetch_backends` 段 (v0.9.3 加), 列出 crwl 是否在 PATH。新加 wechat 子段:

```python
# 在 fetch_backends section 后面新加
wechat_backends_status = _check_wechat_backends()  # 检测 opencli + manifest 含 weixin/download
# JSON shape:
# {"tool": "opencli weixin", "ok": True/False, "detail": "...", "fix_hint": "..."}
```

`_check_wechat_backends()` 检测 (M2 阶段全部生效, 不分阶段 — sources.yml 已经指向 Daily-AC fork, 用户机器装的 OpenCLI 是 fork build, `--stdout` flag M2 push 后立刻有):
1. `shutil.which("opencli")` 存在
2. `opencli weixin download --help` 退出码 0
3. `--stdout` flag 在 help output 里 (grep 一下 `opencli weixin download --help` 的 stdout)

`fix_hint` 给安装命令: `npm i -g github:Daily-AC/OpenCLI` (fork 路径, sources.yml 就是这个)。M2.5 上游 merge 后只影响 source repo 的官方性, 不影响 doctor 检测逻辑 (doctor 看的是用户实际装的 binary 行为, 不是 source repo URL)。

### 7.4 测试 plan

新增测试 (>= +7):

1. `test_fetch_host_routing_wechat()` — mp.weixin.qq.com URL 在 `--backend auto` 下走 `_fetch_via_opencli_weixin`, monkeypatch subprocess.run 返 mock stdout (plain markdown body)
2. `test_fetch_opencli_unavailable()` — `shutil.which` 返 None → backend_unavailable error
3. `test_fetch_opencli_captcha_errorhint()` — mock stdout 是 JSON row with "verification required" → captcha_suspected error
4. `test_fetch_opencli_real_markdown_starts_with_bracket()` — mock stdout 是 `[作者按] 真文章...`, parser 不应误判为 JSON, 走 branch 3 plain markdown 路径成功返
5. `test_fetch_wechat_url_explicit_backend_crwl()` — explicit `--backend crwl` 在 mp.weixin.qq.com URL 上**不走 OpenCLI**, 走 crwl; crwl 返含 "环境异常" → errors 含 `captcha_suspected` (锁死 Q2 explicit-wins 语义)
6. `test_fetch_crwl_captcha_heuristic()` — crwl 在普通 URL 上返含 "Cloudflare" 的 markdown → captcha_suspected error 进 errors (markdown 字段非空, graceful degrade)
7. `test_fetch_jina_captcha_heuristic()` — jina 返含 "Just a moment" → captcha_suspected
8. `test_doctor_wechat_backends_section()` — doctor JSON 输出含 `wechat_backends` key + `opencli weixin download --stdout` 检测条目

**MUST 真 E2E**: 按 CLAUDE.md feedback memory ("即使本次改动只动 contract/normalizer 这类'远离上游'的层, 也要 E2E 一遍受影响的源"), team-lead 在他机器上手跑:

```bash
omnireach fetch https://mp.weixin.qq.com/s/<real-token> --json
```

验返的 markdown 含真文章正文 (作者/标题/正文段落), 不是验证页。

## 8. M2 OpenCLI side 具体改动 diff (predicted)

```diff
--- a/clis/weixin/download.js
+++ b/clis/weixin/download.js
@@ args list @@
     args: [
         { name: 'url', required: true, help: 'WeChat article URL (mp.weixin.qq.com/s/xxx)' },
         { name: 'output', default: './weixin-articles', help: 'Output directory' },
         { name: 'download-images', type: 'boolean', default: true, help: 'Download images locally' },
+        { name: 'stdout', type: 'boolean', default: false, help: 'Print markdown to stdout instead of saving to a file' },
     ],

@@ end of func @@
-        return downloadArticle({...}, {
+        const result = await downloadArticle({...}, {
             output: kwargs.output,
             downloadImages: kwargs['download-images'],
             imageHeaders: { Referer: 'https://mp.weixin.qq.com/' },
             frontmatterLabels: { author: '公众号' },
             detectImageExt: (url) => { ... },
+            stdout: kwargs.stdout,
         });
+        // `--stdout` is a content-streaming mode. Already wrote markdown body
+        // to process.stdout inside downloadArticle(); returning rows would
+        // make Commander append table/JSON output to the same stream.
+        return kwargs.stdout ? null : result;
     },
 });
```

`cli-manifest.json` 也要加对应的 `stdout` 条目到 weixin/download 的 args 数组 — 注意 manifest 文件是 generated/checked-in 二者择一。需要 M2 跑一下 `npm run build` (或 manifest 生成命令, M2 进 OpenCLI repo 看 package.json 确认) 同步。

`clis/weixin/download.test.js` 当前**不存在** (`ls clis/weixin/*.test.js` 只有 search.test.js + drafts.test.js)。M2 新增, 覆盖:
- `--stdout=true` + happy path: 验 `downloadArticle` 收到 `stdout: true` option, 返 null
- `--stdout=true` + errorHint path: 验 errorHint 早返还是走 (不应该被 stdout flag 影响)
- `--stdout=false` (default): 验现有行为不变 — 返 row, output 目录被创建

## 9. 已发布版本 / CLAUDE.md 更新

v0.10.1-alpha entry (M4 时加):

```markdown
- `v0.10.1-alpha` (2026-05-27): **OpenCLI wechat fetch + CAPTCHA detection + host-aware fetch routing** — `omnireach fetch <mp.weixin.qq.com URL>` 现在走 OpenCLI 登录态 Chrome (`opencli weixin download --stdout`) 拿正文 markdown, 替代被验证码拦住的 crwl/jina; 同时给所有 backend 加 CAPTCHA 启发式 (`环境异常 / 完成验证后即可继续访问 / Cloudflare / Just a moment` → errors 含 `captcha_suspected`), 修了 v0.10.0 验证码 silent-fail bug。OpenCLI 这边 `weixin/download` upstream 早就有 (#1250 + 后续), v0.10.1 给它加 `--stdout` flag (mirror 现有 `web/read --stdout` 模式), Daily-AC fork main 直接 push, 同步给 jackwener 提上游 PR。doctor 加 wechat_backends 段。N tests (256 → N).
```

## 10. 永远不做 (自查)

- ❌ 不在 omnireach fetch 这条线塞 LLM (CAPTCHA 检测全部 keyword grep, 零 LLM 依赖)
- ❌ 不 fork omnireach repo (monorepo 拍板, 2026-05-27)
- ❌ 不在 OpenCLI module 截断 markdown (返完整, omnireach `SearchResult.content` 截断只对 search 侧, fetch 不截)
- ❌ 不 commit 任何 cookies / 登录态 / E2E captured wechat content (E2E fixture sanitize)
- ❌ 不 force push 任何分支

## 11. team-lead acks (2026-05-27 session)

1. ✅ **OpenCLI 上游 PR 并行**, 不等 douyin PR #1759 merge。上游 PR description 必须明确 reference PR #1759 作 sibling change: "related to #1759; both expose existing infrastructure to module CLI surface — douyin adds new module, this exposes existing `--stdout` semantics from `ArticleDownloadOptions` already used by `web/read`." 让 jackwener 看到 context 即可, 不绑定 merge order。
2. ✅ **Explicit `--backend` 赢**。Default `auto` 时 mp.weixin.qq.com → 强走 OpenCLI; 用户显式 `--backend crwl` / `--backend jina` 时**尊重 user**, CAPTCHA 启发式兜底 surface 验证页警告。M3 加 click `Choice(["auto", "crwl", "jina", "opencli"])`, 让用户能显式 `--backend opencli`。
3. ✅ **`captcha_suspected` 加 errors[], 不 raise**。markdown 字段保持非空 (我们拿到了响应内容, 只是怀疑是验证页), errors 加 entry, Agent 自己读 errors 决定信不信。SystemExit(1) 仅当所有 backend 都返完全空 content。
4. ✅ **doctor `--stdout` 检测 M2 同步加**, 不分 phasing。sources.yml 已指向 Daily-AC fork, M2 push 后用户机器装的 OpenCLI 立刻有 `--stdout` flag, M2.5 上游 merge 跟 doctor 检测无关。

---

**Status**: spec body 修订完, §5/§7.1/§7.3/§7.4 已按 team-lead review 5 个修订点改完。准备进 M2。
