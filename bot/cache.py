from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from bot import db

CACHE_TTL = {
    "ranked": 30 * 60,
    "lifetime": 60 * 60,
    "recent_matches": 15 * 60,
}


def _payload(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return dict(value)


async def get_or_fetch_view(
    pubg_account_id: str,
    platform: str,
    view: str,
    fetcher: Callable[[], Awaitable[dict[str, Any]]],
) -> tuple[dict[str, Any], bool]:
    cached = await db.get_cache(pubg_account_id, platform, view)
    ttl = CACHE_TTL.get(view, 15 * 60)
    if cached:
        payload, age = cached
        if age < ttl:
            return payload, False

    payload = _payload(await fetcher())
    await db.set_cache(pubg_account_id, platform, view, payload)
    return payload, True


async def invalidate(pubg_account_id: str, platform: str, view: str | None = None) -> None:
    await db.delete_cache(pubg_account_id, platform, view)
