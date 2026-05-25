# omnireach

> 全网通搜索 — 一个 CLI + Claude Code Skill, 给中转站 Agent 用户补齐 WebSearch + 多平台读取能力.

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
pipx install omnireach
omnireach init       # 自动装好 agent-reach 等零配置依赖
omnireach "Claude 4.7 prompt caching 实测"
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

| 源            | 类型                              | 配置方式                                  |
|---------------|-----------------------------------|-------------------------------------------|
| web           | 免费 (零配置)                     | 默认启用                                  |
| hackernews    | 免费 (零配置)                     | 默认启用                                  |
| youtube       | 免费 (零配置)                     | 默认启用                                  |
| github        | 免费 (零配置)                     | 默认启用                                  |
| rss           | 免费 (零配置)                     | 默认启用                                  |
| wechat        | 免费 (微信公众号, 零配置)         | 默认启用                                  |
| bilibili      | 免费 (B 站, 零配置)               | 默认启用                                  |
| reddit        | 免费 (一步配置)                   | `omnireach setup reddit` (OAuth)          |
| twitter       | 免费 (重配置, v0.3)               | `omnireach setup twitter` (Chrome 扩展)   |
| xiaohongshu   | 免费 (小红书, 重配置, v0.3)       | `omnireach setup xiaohongshu`             |
| 💎 tavily     | 付费 (Tavily Search API)          | env `TAVILY_API_KEY`                      |
| 💎 brave      | 付费 (Brave Search API)           | env `BRAVE_API_KEY`                       |
| 💎 perplexity | 付费 (Perplexity Sonar)           | env `PERPLEXITY_API_KEY`                  |

## 💎 付费 booster (v0.4)

omnireach 默认完全免费。如果你愿意配置付费 API Key，结果质量会更高：

```bash
omnireach setup tavily       # 引导拿 Key + 写入 ~/.omnireach/secrets.env
omnireach setup brave
omnireach setup perplexity
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
