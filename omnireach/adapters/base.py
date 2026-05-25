"""AdapterBase — every source adapter inherits this."""

from __future__ import annotations

from abc import ABC, abstractmethod

from omnireach.contract import SearchResult


class AdapterUnavailable(Exception):
    """Raised when an adapter's upstream binary / auth is missing."""

    def __init__(self, source: str, reason: str, *, hint: str | None = None) -> None:
        super().__init__(f"adapter {source} unavailable: {reason}")
        self.source = source
        self.reason = reason
        self.hint = hint


class AdapterBase(ABC):
    """Contract every adapter must satisfy.

    Adapters are responsible for: (1) checking whether their upstream is
    reachable (`is_ready`) and (2) translating an upstream call's output
    into a list of normalized SearchResult.
    """

    name: str = ""           # override in subclass; matches sources.yml id
    requires: list[str] = []  # CLI binaries / pip pkgs the adapter needs

    @abstractmethod
    async def is_ready(self) -> bool:
        """Cheap probe: returns True if .search() is likely to succeed."""

    @abstractmethod
    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        """Run a search. Must raise AdapterUnavailable rather than returning [] on auth/missing-bin."""
