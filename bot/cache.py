from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from bot import db

CACHE_TTL = {
    "ranked": 30 * 60,
    "lifetime": 60 * 60,
    "recent_matches": 15 * 60,
    "source-ranked:": 30 * 60,
    "source-lifetime:": 60 * 60,
    "source-recent:": 15 * 60,
    "source-mastery": 60 * 60,
    "profile-overview:": 10 * 60,
    "profile-ranked:": 10 * 60,
    "profile-lifetime:": 10 * 60,
    "profile-recent:": 10 * 60,
    "profile-mastery:": 10 * 60,
    "profile-analysis:": 10 * 60,
    "profile-full:": 10 * 60,
}


def _payload(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    if isinstance(value, dict):
        return dict(value)
    return value


def _ttl_for_view(view: str, ttl: int | None = None) -> int:
    if ttl is not None:
        return ttl
    if view in CACHE_TTL:
        return CACHE_TTL[view]
    for prefix, prefix_ttl in CACHE_TTL.items():
        if view.startswith(prefix):
            return prefix_ttl
    return 15 * 60


async def get_or_fetch_view(
    pubg_account_id: str,
    platform: str,
    view: str,
    fetcher: Callable[[], Awaitable[Any]],
    *,
    ttl: int | None = None,
) -> tuple[Any, bool]:
    cached = await db.get_cache(pubg_account_id, platform, view)
    ttl_seconds = _ttl_for_view(view, ttl)
    if cached:
        payload, age = cached
        if age < ttl_seconds:
            return payload, False

    payload = _payload(await fetcher())
    await db.set_cache(pubg_account_id, platform, view, payload)
    return payload, True


async def invalidate(pubg_account_id: str, platform: str, view: str | None = None) -> None:
    await db.delete_cache(pubg_account_id, platform, view)
