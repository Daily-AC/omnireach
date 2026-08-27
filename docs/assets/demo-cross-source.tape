# CSDN 演示 — 零配置微信公众号搜索 + 跨源统一 schema
# 渲染: env HOME=$(mktemp -d) EXA_API_KEY= TAVILY_API_KEY= BRAVE_API_KEY= PERPLEXITY_API_KEY= vhs docs/assets/demo-cross-source.tape
# 必须隔离 HOME：本机 ~/.omnireach/preferences.toml 的 boosters.auto_enable 会让 wechat 走 exa-api 而非零配置的 sogou
Output docs/assets/demo-cross-source.gif

Set WindowBar Colorful
Set BorderRadius 10
Set Margin 24
Set MarginFill "#6f9fc4"
Set Width 1280
Set Height 450
Set FontSize 17
Set Theme "Catppuccin Mocha"
Set Padding 18
Set TypingSpeed 30ms
Set Framerate 24
Set WaitTimeout 40s

Sleep 600ms
Type "# 装完就能搜微信公众号 —— 不用 key，不用登录"
Enter
Sleep 600ms

Type `omnireach search --on wechat --limit 3 "Claude Code" | jq -r '.results[]|"\(.adapter)  \(.author)  \(.title)"'`
Enter
Wait
Sleep 2500ms

Type "# 换个源，同一套 schema"
Enter
Sleep 600ms

Type `omnireach search --on hackernews --limit 3 "MCP" | jq -r '.results[]|"\(.source)  \(.title)"'`
Enter
Wait
Sleep 3500ms
