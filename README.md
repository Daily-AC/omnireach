# omnireach

> 全网通搜索 — 一个 CLI + Claude Code Skill, 给中转站 Agent 用户补齐 WebSearch + 多平台读取能力.

> **Works with**: Claude Code · Antigravity (`agy`) · 任何识别 `.claude-plugin/` manifest 的 Agent CLI。
> v0.5.1 实测过 `agy plugin install` 走通完整 SKILL 路由流程。

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)

## 为什么需要 omnireach

中转站 (cliproxy / anyrouter / 各种 OpenAI 兼容代理) 让国内同学绕开付费、能调多模型, 但代价是丢掉了 Anthropic 服务端工具, 其中 **WebSearch** 是损失最重的一项:

- 想搜 Twitter 上的实时讨论? 原生 WebSearch 几乎抓不到
- 想看 Reddit / HN 的深度评论? 拿不到
- 想读 YouTube 字幕、小红书种草、B 站技术视频? 完全不可达

omnireach 把社区里已经成熟的三个上游工具 (**Agent-Reach** / **OpenCLI** / **last30days**) 当可插拔引擎调用, 对外只暴露一个轻量 CLI + 一个 Claude Skill, 实现 **3 分钟内**装好就能搜全网.

## 快速开始

```bash
uv tool install git+https://github.com/Daily-AC/omnireach.git
omnireach init                  # 写默认 ~/.omnireach/preferences.toml
omnireach search "vibe coding"  # HN 立即可用 (零配置)
```

零配置只跑 HackerNews。要打开其他源:

```bash
omnireach setup youtube   # pip install yt-dlp
omnireach setup github    # 提示 brew install gh (macOS)
omnireach setup reddit    # uv tool install rdt-cli + rdt login
omnireach setup exa       # 拿 EXA_API_KEY (付费 web search)
```

### 在 Claude Code 里用

```
/plugin marketplace add Daily-AC/omnireach
/plugin install omnireach
```

然后在对话里直接说: "用 omnireach 搜一下 ..."

## 命令

| 命令 | 干嘛 |
|---|---|
| `omnireach search "<query>"` | 搜索 |
| `omnireach search --on twitter,reddit "..."` | 指定源 |
| `omnireach search --mode quick "..."` | 只查 web + hn |
| `omnireach search --mode deep "..."` | 查所有就绪源 |
| `omnireach search --json "..."` | 输出 JSON 给下游 pipe |
| `omnireach init` | 安装零配置依赖 |
| `omnireach sources` | 列出所有源 + 心愿单状态 |
| `omnireach setup <source>` | 引导式配置一个 🟡 / 🔴 源 (Agent 装上游 + 你完成认证) |
| `omnireach doctor` | 健康检查 |

## 支持的源

| 源 | tier | 依赖 | 说明 |
|---|---|---|---|
| hackernews | ✅ ready | 无 | 直连 Algolia, 零配置 |
| youtube | ✅ ready | `yt-dlp` (pip install) | `omnireach setup youtube` |
| github | ✅ ready | `gh` CLI + `gh auth login` | `omnireach setup github` |
| rss | ✅ ready | 内置 feedparser | query 必须是 URL |
| reddit | 🟡 one_step | `rdt-cli` + `rdt login` | `omnireach setup reddit` |
| twitter | 🔴 heavy | OpenCLI + Chrome 扩展 | v0.3 路径 |
| xiaohongshu | 🔴 heavy | OpenCLI + Chrome 扩展 | v0.3 路径 |
| tiktok | 🔴 heavy | OpenCLI + Chrome 扩展 | TikTok 国际版 (v0.7); 抖音见下方 issue #12 |
| 💎 tavily | booster | env `TAVILY_API_KEY` | 付费 (v0.4) |
| 💎 brave | booster | env `BRAVE_API_KEY` | 付费 (v0.4) |
| 💎 perplexity | booster | env `PERPLEXITY_API_KEY` | 付费 (v0.4) |
| 💎 exa | booster | env `EXA_API_KEY` | 付费 web search (v0.5) |
| 💎 wechat | booster | env `EXA_API_KEY` | 微信公众号 (Exa domain-filtered, v0.6) |
| 💎 bilibili | booster | env `EXA_API_KEY` | B站 (Exa domain-filtered, v0.6) |

> **抖音 (douyin.com)**: 暂未直接支持。OpenCLI 现有 `douyin` adapter 只覆盖创作者后台 (creator.douyin.com)，没有 keyword search。我们正在给 OpenCLI 提 douyin search PR，merge 后会跟进加进来 (issue #12)。要海外短视频可以先用 tiktok。

> v0.4 及之前曾把 `web` 列为零配置, 实际不可用 (v0.1 起就是 architecture bug — 详见 `docs/superpowers/specs/2026-05-26-omnireach-v0.5-design.md`)。v0.5 起 web search 走 💎 exa booster (或任一付费 booster)。

## 升级

omnireach 还在 alpha 频繁迭代。检查 + 升级:

```bash
omnireach check-update                                                            # 比对 GitHub Releases
uv tool install --force git+https://github.com/Daily-AC/omnireach.git             # 拉最新
```

> ⚠️  `uv tool upgrade omnireach` **不会**拉新 commit (uv 把 git URL 装的工具锁在 install 时的 commit 上). `--force` 重装才会去 fetch 最新.

## 上游依赖

omnireach 不再在运行时调用任何 wrapper。每个 adapter 直接 shell 出对应上游 binary (yt-dlp / gh / rdt-cli) 或调用 Python 库 (feedparser)。每个 binary 用 `omnireach setup <X>` 引导安装。

一次性装齐 (可选, 不强制):

```bash
uv tool install git+https://github.com/Panniantong/Agent-Reach.git
agent-reach install --channels youtube,github,reddit
```

Agent-Reach 是上游 installer/doctor 工具, 完全可选 — omnireach 自己 doctor/search 都不依赖它。

## 🪟 平台支持

| 平台 | 状态 | 说明 |
|---|---|---|
| macOS | ✅ 主要开发平台 | 全部源测试过 (HN/RSS/youtube/github/reddit/twitter/xhs + 4 booster + wechat/bilibili) |
| Linux | 🟡 best-effort | 应能 work；setup 流程对 `apt`/`pacman` 不自动 |
| WSL2 | 🟡 best-effort | 跟 Linux 一样 |
| Windows (原生 PowerShell) | 🟡 实验性 (v0.6.3+) | 代码已 macOS-假设解耦：secrets.env 不再调 POSIX chmod；preferences edit fallback notepad；setup github 提示加 `winget install GitHub.cli`；OpenCLI 类源 (twitter/xhs) 跨平台理论可用但未实测。**遇到问题请提 issue**。 |

跑 `omnireach doctor` 会在顶部打印一行 platform / Python 版本，方便提 issue 时附上。

## 💎 付费 booster (v0.4)

omnireach 默认完全免费。如果你愿意配置付费 API Key，结果质量会更高：

```bash
omnireach setup tavily       # 引导拿 Key + 写入 ~/.omnireach/secrets.env
omnireach setup brave
omnireach setup perplexity
omnireach setup exa          # v0.5 新增 (替代旧 web 源)
```

检测到 Key 后自动启用。结果元数据 `cost="paid"`，TTY 显示前缀 💎，便于审计。

要禁用：编辑 `~/.omnireach/preferences.toml` 设 `[boosters] auto_enable = false`。

## ⚙️ 用户偏好 (v0.4)

`~/.omnireach/preferences.toml` 可配置默认源、语言、输出格式、source_trust 覆盖。

```bash
omnireach preferences show     # 查看当前配置
omnireach preferences edit     # 用 $EDITOR 编辑
omnireach preferences reset    # 重置 (备份原文件到 .bak)
omnireach preferences path     # 打印文件位置
```

## 设计

详见 `docs/superpowers/specs/2026-05-25-omnireach-design.md`.

## License

MIT — 见 [LICENSE](LICENSE).
