"""Terminal-independent omnireach search application service."""

from __future__ import annotations

import os

from omnireach.contract import SearchEnvelope, SourceError
from omnireach.dispatcher import Dispatcher
from omnireach.normalizer import build_envelope
from omnireach.registry import Registry, load_registry
from omnireach.router import RouteRequest, Router
from omnireach.scorer import rank

BOOSTER_KEY_ENV = {
    "tavily": "TAVILY_API_KEY",
    "brave": "BRAVE_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "exa": "EXA_API_KEY",
    "wechat": "EXA_API_KEY",
    "bilibili": "EXA_API_KEY",
}


def augment_with_active_boosters(
    source_ids: list[str],
    registry: Registry,
    explicit_sources: list[str] | None,
) -> list[str]:
    """Add configured boosters only for automatic routing."""
    if explicit_sources:
        return list(source_ids)
    output = list(source_ids)
    for source_id, env_name in BOOSTER_KEY_ENV.items():
        if not os.environ.get(env_name) or source_id in output:
            continue
        try:
            registry.get(source_id)
        except KeyError:
            continue
        output.append(source_id)
    return output


async def search(
    query: str,
    *,
    sources: list[str] | None = None,
    mode: str = "auto",
    limit: int = 10,
    timeout: float = 30.0,
) -> SearchEnvelope:
    """Search routed sources and return the stable domain envelope."""
    registry = load_registry()
    if sources:
        known = {source.id for source in registry.sources}
        unknown = [source for source in sources if source not in known]
        if unknown:
            raise ValueError(f"unknown source: {', '.join(unknown)}")

    route = Router(registry).plan(
        RouteRequest(query=query, explicit_sources=sources, mode=mode)
    )
    source_ids = augment_with_active_boosters(
        route.source_ids, registry, sources
    )

    adapters = {}
    load_errors: list[SourceError] = []
    for source_id in source_ids:
        try:
            spec = registry.get(source_id)
            adapters[source_id] = spec.load_adapter_class()()
        except Exception as exc:  # noqa: BLE001
            load_errors.append(
                SourceError(
                    source=source_id,
                    error=f"adapter load failed: {exc}",
                    category="failed",
                )
            )

    dispatcher = Dispatcher(
        timeout=timeout,
        per_source_limit=limit,
        timeouts_by_source={
            source.id: source.timeout_seconds for source in registry.sources
        },
    )
    results, errors = await dispatcher.run(adapters, query)
    ranked = rank(
        results,
        trust_map={source.id: source.trust for source in registry.sources},
    )
    return build_envelope(
        query=query,
        results=ranked,
        errors=[*load_errors, *errors],
    )
