"""Doctor — probe each source's readiness."""

from __future__ import annotations

from dataclasses import dataclass

from omnireach.registry import load_registry


@dataclass
class SourceStatus:
    source: str
    tier: str
    ok: bool
    detail: str = ""


async def run_doctor() -> list[SourceStatus]:
    reg = load_registry()
    statuses: list[SourceStatus] = []
    for spec in reg.sources:
        try:
            cls = spec.load_adapter_class()
            ok = await cls().is_ready()
            statuses.append(SourceStatus(spec.id, spec.tier, ok, "" if ok else "not ready"))
        except Exception as e:  # noqa: BLE001
            statuses.append(SourceStatus(spec.id, spec.tier, False, str(e)))
    return statuses
