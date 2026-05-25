"""Source Registry — loads sources.yml, exposes typed access."""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REGISTRY_PATH = Path(__file__).parent / "sources.yml"


@dataclass
class Dep:
    kind: str
    name: str = ""
    step: str = ""
    verify: str = ""


@dataclass
class SourceSpec:
    id: str
    tier: str  # ready | one_step | heavy
    adapter: str  # dotted import path
    description: str
    query_hints: list[str] = field(default_factory=list)
    default_in_auto: bool = False
    deps_auto: list[Dep] = field(default_factory=list)
    deps_manual: list[Dep] = field(default_factory=list)

    def load_adapter_class(self):
        module_path, _, cls_name = self.adapter.rpartition(".")
        mod = importlib.import_module(module_path)
        return getattr(mod, cls_name)


@dataclass
class Registry:
    sources: list[SourceSpec]

    def get(self, source_id: str) -> SourceSpec:
        for s in self.sources:
            if s.id == source_id:
                return s
        raise KeyError(source_id)

    def default_auto_sources(self) -> list[SourceSpec]:
        return [s for s in self.sources if s.default_in_auto]

    def sources_matching_hints(self, query: str) -> list[SourceSpec]:
        q = query.lower()
        out: list[SourceSpec] = []
        for s in self.sources:
            if any(h.lower() in q for h in s.query_hints):
                out.append(s)
        return out


def load_registry(path: Path | None = None) -> Registry:
    path = path or REGISTRY_PATH
    raw = yaml.safe_load(path.read_text())
    sources: list[SourceSpec] = []
    for entry in raw:
        deps = entry.get("deps") or {}
        spec = SourceSpec(
            id=entry["id"],
            tier=entry["tier"],
            adapter=entry["adapter"],
            description=entry["description"],
            query_hints=entry.get("query_hints", []),
            default_in_auto=entry.get("default_in_auto", False),
            deps_auto=[Dep(**d) for d in (deps.get("auto") or [])],
            deps_manual=[Dep(**d) for d in (deps.get("manual") or [])],
        )
        sources.append(spec)
    return Registry(sources=sources)
