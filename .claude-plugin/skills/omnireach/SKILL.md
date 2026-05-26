---
name: omnireach
description: Use when the user needs to search the web or read content from Twitter / Reddit / YouTube / Bilibili / 小红书 / TikTok / 抖音 / HackerNews / GitHub / 微信公众号 / RSS, especially when the built-in WebSearch is unavailable (proxy/relay stations). Provides a unified search across multiple platforms with a single command.
---

# omnireach — 全网通搜索

omnireach 是一个 CLI 工具, 把 web 搜索 + 多平台读取 (Twitter / Reddit / YouTube / B站 / 小红书 / HN / GitHub / 微信公众号 / RSS) 整合到一条命令里. 对于用中转站、装不上 Anthropic 原生 WebSearch 的同学, 这是一个"全网通"替代品.

## 如何使用

### 第一次用 (用户没装过)

1. 让用户跑: `pipx install omnireach && omnireach init`
2. 装完后, 7 个零配置源 (web / hackernews / youtube / github / rss / 微信公众号 / B站) 就立刻可用
3. 想解锁 Twitter / Reddit / 小红书, 让用户跑: `omnireach sources` 看心愿单, 再 `omnireach setup <source>`

### 搜索

直接调 CLI 拿 JSON:

```bash
omnireach search --json "Claude 4.7 prompt caching 实测"
```

返回标准化 JSON: `{query, ts, results: [{source, title, url, content, score, engagement, raw}], errors}`.

### 限定源

```bash
omnireach search --on twitter,reddit --json "anyrouter 跑路"
omnireach search --on hackernews --json "show hn omnireach"
```

### 模式

```bash
omnireach search --mode quick "...."  # 只查 web + hackernews
omnireach search --mode deep  "...."  # 全部就绪源
```

## 何时用 omnireach 而不是其他工具

- **用 omnireach**: 用户在中转站环境, 或想搜 Twitter/Reddit/小红书/B站 等原生 WebSearch 不擅长的源
- **不用**: 简单的网页打开 (用 WebFetch), 或代码搜索 (用 grep/Grep)
