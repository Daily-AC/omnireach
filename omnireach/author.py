"""Creator-catalog application service — "what did this account itself post".

Keyword search answers "who mentioned X", which for a creator query is mostly
other people's fan edits and reaction videos. This service answers the other
question, and shares the CLI/MCP entry points the way `service.search` does.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from omnireach.adapters.base import AdapterUnavailable
from omnireach.contract import AuthorEnvelope, SourceError
from omnireach.registry import load_registry

AUTHOR_SOURCES = ("douyin",)
MAX_AUTHOR_LIMIT = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def failed_author_envelope(
    query: str, source: str, message: str, category: str = "failed",
) -> AuthorEnvelope:
    """The one shape a creator-catalog failure takes, wherever it is caught."""
    return AuthorEnvelope(
        query=query,
        ts=_now(),
        errors=[SourceError(source=source, error=message, category=category)],
    )


async def author_catalog(
    handle: str,
    *,
    source: str = "douyin",
    limit: int = 20,
    order: Literal["recent", "likes"] = "recent",
    include_media_urls: bool = False,
    timeout: float = 180.0,
) -> AuthorEnvelope:
    """List one creator's own works from a source that supports catalogs."""
    if not isinstance(handle, str) or not handle.strip():
        raise ValueError("handle must be a non-empty string")
    if source not in AUTHOR_SOURCES:
        raise ValueError(
            f"source {source!r} has no creator catalog; "
            f"supported: {', '.join(AUTHOR_SOURCES)}"
        )
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_AUTHOR_LIMIT:
        raise ValueError(f"limit must be an integer between 1 and {MAX_AUTHOR_LIMIT}")
    if order not in {"recent", "likes"}:
        raise ValueError("order must be recent or likes")

    handle = handle.strip()
    try:
        adapter = load_registry().get(source).load_adapter_class()()
    except Exception as exc:  # noqa: BLE001
        return failed_author_envelope(handle, source, f"adapter load failed: {exc}")

    author = getattr(adapter, "author", None)
    if author is None:
        return failed_author_envelope(handle, source, f"{source} adapter has no creator catalog")

    try:
        identity, results, stats = await author(
            handle,
            limit=limit,
            order=order,
            include_media_urls=include_media_urls,
            timeout=timeout,
        )
    except AdapterUnavailable as exc:
        message = exc.reason if not exc.hint else f"{exc.reason} — {exc.hint}"
        return failed_author_envelope(handle, source, message, category="unavailable")
    except Exception as exc:  # noqa: BLE001
        return failed_author_envelope(handle, source, str(exc))

    envelope = AuthorEnvelope(
        query=handle,
        ts=_now(),
        author=identity,
        order=stats["order"],
        scanned=stats["scanned"],
        complete=stats["complete"],
        results=results,
    )
    if identity.resolved_from == "search":
        envelope.warnings.append(
            f"Resolved {handle!r} to {identity.name!r} ({identity.id}) by follower "
            "count; pass the profile URL to pin an exact account"
        )
    if order == "likes" and not envelope.complete:
        envelope.warnings.append(
            f"Ranked by likes over only {envelope.scanned} works because paging "
            "stopped before the end of the catalog; the top of this list may be "
            "incomplete"
        )
    return envelope


__all__ = [
    "AUTHOR_SOURCES",
    "MAX_AUTHOR_LIMIT",
    "author_catalog",
    "failed_author_envelope",
]
