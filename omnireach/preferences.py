"""User preferences: ~/.omnireach/preferences.toml."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Defaults(BaseModel):
    model_config = ConfigDict(extra="forbid")
    on: list[str] = Field(default_factory=lambda: ["web", "hackernews", "reddit", "twitter"])
    exclude: list[str] = Field(default_factory=list)
    lang: str = "zh-CN"


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: str = "tty"
    max_results_per_source: int = 8


class Boosters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    auto_enable: bool = True


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    defaults: Defaults = Field(default_factory=Defaults)
    output: Output = Field(default_factory=Output)
    boosters: Boosters = Field(default_factory=Boosters)
    trust_overrides: dict[str, float] = Field(default_factory=dict)


DEFAULT_PREFERENCES_TOML = """\
# omnireach preferences — 编辑后用 `omnireach preferences show` 验证

[defaults]
# 默认参与 fanout 的源（CLI --on 会覆盖）
on      = ["web", "hackernews", "reddit", "twitter"]
exclude = []                  # 始终排除的源
lang    = "zh-CN"             # 透传到 web/wechat 等

[output]
format                 = "tty"   # tty | json
max_results_per_source = 8

[boosters]
# false 表示即使配了 Key 也不调用付费源
auto_enable = true

[trust_overrides]
# 覆盖 sources.yml 的默认 source_trust（0.0-1.0）
# web = 0.80
"""


def preferences_path() -> Path:
    return Path.home() / ".omnireach" / "preferences.toml"


def load_preferences(path: Path | None = None) -> Preferences:
    path = path or preferences_path()
    if not path.exists():
        return Preferences()
    try:
        data = tomllib.loads(path.read_text())
        return Preferences.model_validate(data)
    except (tomllib.TOMLDecodeError, ValidationError) as e:
        print(
            f"warning: preferences.toml invalid ({e}); 使用默认值。"
            f"编辑文件: {path}",
            file=sys.stderr,
        )
        return Preferences()


def write_default_preferences(path: Path | None = None) -> None:
    path = path or preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_PREFERENCES_TOML)
