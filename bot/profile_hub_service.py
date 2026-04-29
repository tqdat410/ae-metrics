from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bot import cache, db
from bot.profile_metrics import analyze_profile, summarize_recent
from bot.rate_limiter import throttle

RECENT_WINDOW = 20


class ProfileHubService:
    def __init__(self, provider: Any) -> None:
        self.provider = provider

    async def build(self, account: Any) -> dict[str, Any]:
        season_id = await self.provider.get_current_season(account.region)
        key = f"profile-overview:{season_id}"

        async def fetcher() -> dict[str, Any]:
            ranked = await self._ranked_source(account, season_id)
            lifetime = await self._lifetime_source(account)
            metadata = await self._metadata_source(account)
            mastery = await self._mastery_source(account)
            recent = await self._recent_source(account)
            analysis = analyze_profile(recent)
            return {
                "view": "overview",
                "season_id": season_id,
                "generated_at": _now_iso(),
                "metadata": metadata,
                "ranked": ranked,
                "lifetime": lifetime,
                "mastery": mastery,
                "recent": recent,
                "analysis": analysis,
            }

        payload, _ = await cache.get_or_fetch_view(account.account_id, account.region, key, fetcher)
        return payload

    async def _ranked_source(self, account: Any, season_id: str) -> dict[str, Any]:
        key = f"source-ranked:all:{season_id}"

        async def fetcher() -> dict[str, Any]:
            await throttle("pubg_ranked")
            payload = await self.provider.fetch_ranked_view(account, mode="all", season_id=season_id)
            await db.upsert_stat_snapshot(account.account_id, account.region, "ranked", _now_iso(), payload)
            return payload

        payload, _ = await cache.get_or_fetch_view(account.account_id, account.region, key, fetcher)
        return payload

    async def _lifetime_source(self, account: Any) -> dict[str, Any]:
        key = "source-lifetime:all"

        async def fetcher() -> dict[str, Any]:
            await throttle("pubg_lifetime")
            payload = await self.provider.fetch_lifetime_view(account, mode="all")
            await db.upsert_stat_snapshot(account.account_id, account.region, "lifetime", _now_iso(), payload)
            return payload

        payload, _ = await cache.get_or_fetch_view(account.account_id, account.region, key, fetcher)
        return payload

    async def _metadata_source(self, account: Any) -> dict[str, Any]:
        async def fetcher() -> dict[str, Any]:
            await throttle("pubg_player")
            return await self.provider.fetch_account_metadata(account)

        payload, _ = await cache.get_or_fetch_view(account.account_id, account.region, "source-account", fetcher)
        return payload

    async def _mastery_source(self, account: Any) -> dict[str, Any]:
        async def fetcher() -> dict[str, Any]:
            await throttle("pubg_mastery")
            return await self.provider.fetch_mastery_view(account)

        payload, _ = await cache.get_or_fetch_view(account.account_id, account.region, "source-mastery", fetcher)
        return payload

    async def _recent_source(self, account: Any) -> dict[str, Any]:
        key = f"source-recent:{RECENT_WINDOW}"

        async def fetcher() -> dict[str, Any]:
            return summarize_recent(await self._recent_matches(account, RECENT_WINDOW), "all", RECENT_WINDOW)

        payload, _ = await cache.get_or_fetch_view(account.account_id, account.region, key, fetcher)
        return summarize_recent(payload.get("matches") or [], "all", RECENT_WINDOW)

    async def _recent_matches(self, account: Any, limit: int) -> list[dict[str, Any]]:
        await throttle("pubg_matches")
        recent_ids = await self.provider.fetch_recent_match_ids(account, limit=max(limit, 10))
        cursor = await db.get_match_cursor(account.account_id, account.region) or {}
        seen_ids = set(cursor.get("recent_match_ids") or [])
        for match_id in recent_ids:
            if match_id in seen_ids:
                continue
            await db.upsert_match_summary(await self.provider.fetch_match_summary(account, match_id))
        await db.set_match_cursor(account.account_id, account.region, {"recent_match_ids": recent_ids, "fetched_at": _now_unix()})
        stored = await db.list_recent_match_summaries(account.account_id, account.region, limit=max(limit, 10))
        if stored:
            return stored
        return [await self.provider.fetch_match_summary(account, match_id) for match_id in recent_ids[:limit]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_unix() -> int:
    return int(datetime.now(timezone.utc).timestamp())
