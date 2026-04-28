from __future__ import annotations

from typing import Any, Protocol

from bot import db

CACHE_TTL = {"lol": 900, "valo": 900, "pubg": 1800}


class RankProvider(Protocol):
    async def fetch_rank(self, account: Any) -> Any: ...


def _rank_from_payload(payload: dict[str, Any], provider: RankProvider | None = None) -> Any:
    rank_type = getattr(provider, "RankInfo", None)
    if rank_type:
        return rank_type(**payload)
    return payload


def _rank_payload(rank: Any) -> dict[str, Any]:
    if hasattr(rank, "to_dict"):
        return rank.to_dict()
    if hasattr(rank, "__dict__"):
        return dict(rank.__dict__)
    return dict(rank)


async def get_or_fetch_rank(discord_id: int, game: str, account: Any, provider: RankProvider) -> Any:
    cached = await db.get_cache(discord_id, game)
    ttl = CACHE_TTL.get(game, 900)
    if cached:
        payload, age = cached
        if age < ttl:
            return _rank_from_payload(payload, provider)

    rank = await provider.fetch_rank(account)
    await db.set_cache(discord_id, game, _rank_payload(rank))
    return rank


async def invalidate(discord_id: int, game: str) -> None:
    await db.delete_cache(discord_id, game)
