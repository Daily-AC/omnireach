"""Router — picks which sources to fan out to for a given query."""

from __future__ import annotations

from dataclasses import dataclass

from omnireach.registry import Registry

MAX_SOURCES = 5


@dataclass
class RouteRequest:
    query: str
    explicit_sources: list[str] | None = None  # --on flag
    mode: str = "auto"  # auto | quick | deep


@dataclass
class Route:
    source_ids: list[str]
    rationale: str  # short explanation for --verbose


class Router:
    def __init__(self, registry: Registry) -> None:
        self.registry = registry

    def plan(self, req: RouteRequest) -> Route:
        if req.explicit_sources:
            valid = [s.id for s in self.registry.sources]
            chosen = [s for s in req.explicit_sources if s in valid]
            return Route(source_ids=chosen, rationale="explicit --on")

        if req.mode == "quick":
            return Route(source_ids=["web", "hackernews"], rationale="mode=quick")

        if req.mode == "deep":
            all_ready = [s.id for s in self.registry.sources if s.tier == "ready"]
            return Route(source_ids=all_ready[:MAX_SOURCES], rationale="mode=deep")

        # auto: hint matches first, then default
        hinted = [s.id for s in self.registry.sources_matching_hints(req.query)]
        defaults = [s.id for s in self.registry.default_auto_sources()]
        merged: list[str] = []
        for sid in hinted + defaults:
            if sid not in merged:
                merged.append(sid)
            if len(merged) >= MAX_SOURCES:
                break
        return Route(source_ids=merged, rationale="auto: hints + defaults")
