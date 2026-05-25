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

✅ **零配置 (7 个)**: `web` · `hackernews` · `youtube` · `github` · `rss` · `wechat` (微信公众号) · `bilibili` (B 站)

🟡 **一步配置 (1 个, v0.2 新增)**: `reddit` — 跑 `omnireach setup reddit`, Agent 自动装 rdt-cli, 你完成 OAuth

🔴 计划中 (v0.3+): `twitter` · `xiaohongshu` (小红书)

## 设计

详见 `docs/superpowers/specs/2026-05-25-omnireach-design.md`.

## License

MIT — 见 [LICENSE](LICENSE).
