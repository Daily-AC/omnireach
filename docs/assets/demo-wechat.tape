# VHS tape — zero-config WeChat search demo
# Render: EXA_API_KEY="" TAVILY_API_KEY="" BRAVE_API_KEY="" PERPLEXITY_API_KEY="" vhs demo-wechat.tape
Output docs/assets/demo-wechat.gif

Set FontSize 17
Set Width 1200
Set Height 640
Set Theme "Catppuccin Mocha"
Set Padding 16
Set TypingSpeed 40ms

Type "# Your agent can't search WeChat official accounts. omnireach can — zero config:"
Enter
Sleep 800ms
Type `omnireach search --on wechat --limit 3 "Claude Code 技巧"`
Enter
Sleep 12s

Type "# Different source, same JSON schema. Piped output is auto-JSON — agent-ready:"
Enter
Sleep 800ms
Type `omnireach search --on bilibili --limit 2 "Claude Code" | jq '.results[] | {source, title, url, engagement}'`
Enter
Sleep 12s
Sleep 3s
