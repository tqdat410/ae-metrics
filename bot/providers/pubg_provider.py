from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from urllib.parse import quote

import httpx

from bot import db
from bot.config import get_settings
from bot.http_client import get_client
from bot.providers import AccountInfo, NotFoundError, RankInfo, UpstreamError, handle_response, upstream_error

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://api.pubg.com"
SEASON_TTL_SECONDS = 7 * 24 * 60 * 60
PREFERRED_GAME_MODES = ("squad-fpp", "squad", "duo-fpp", "duo", "solo-fpp", "solo")


class PubgProvider:
    RankInfo = RankInfo

    def __init__(self, client: httpx.AsyncClient | None = None, api_key: str | None = None) -> None:
        self._client = client or get_client()
        self._api_key = api_key or get_settings().pubg_api_key

    async def lookup_account(self, name: str, tag: str | None = None, region: str = "steam") -> AccountInfo:
        del tag
        platform = region.lower()
        url = f"{BASE_URL}/shards/{quote(platform, safe='')}/players"
        payload = await self._get_json(url, "PUBG player", params={"filter[playerNames]": name})
        players = payload.get("data") or []
        if not players:
            raise NotFoundError(f"PUBG player not found: {name}")

        player = players[0]
        account_id = player.get("id")
        if not account_id:
            raise UpstreamError("PUBG player payload missing account id")
        attributes = player.get("attributes") or {}
        canonical_name = attributes.get("name") or name
        return AccountInfo(None, None, account_id, canonical_name, None, platform)

    async def fetch_rank(self, account: AccountInfo) -> RankInfo:
        ranked = await self.fetch_ranked_view(account)
        return RankInfo(
            ranked.get("tier"),
            ranked.get("division"),
            ranked.get("points"),
            ranked.get("wins"),
            None,
            ranked,
        )

    async def fetch_ranked_view(self, account: AccountInfo) -> dict:
        if not account.account_id:
            raise NotFoundError("PUBG account has no account id")

        season_id = await self._get_current_season(account.region)
        url = (
            f"{BASE_URL}/shards/{quote(account.region, safe='')}/players/"
            f"{quote(account.account_id, safe='')}/seasons/{quote(season_id, safe='')}/ranked"
        )
        payload = await self._get_json(url, "PUBG ranked stats")
        stats = (payload.get("data") or {}).get("attributes", {}).get("rankedGameModeStats", {})
        mode, ranked = self._preferred_mode_stats(stats)
        tier = ranked.get("currentTier") or {}
        return {
            "view": "ranked",
            "mode": mode,
            "season_id": season_id,
            "tier": tier.get("tier"),
            "division": tier.get("subTier"),
            "points": ranked.get("currentRankPoint"),
            "wins": ranked.get("roundsWon"),
            "matches": ranked.get("roundsPlayed"),
            "top10s": ranked.get("top10s"),
            "kills": ranked.get("kills"),
            "kd": ranked.get("kdr"),
            "damage": ranked.get("damageDealt"),
            "avg_survival_time": ranked.get("avgSurvivalTime"),
            "raw": ranked or payload,
        }

    async def fetch_lifetime_view(self, account: AccountInfo) -> dict:
        if not account.account_id:
            raise NotFoundError("PUBG account has no account id")

        url = (
            f"{BASE_URL}/shards/{quote(account.region, safe='')}/players/"
            f"{quote(account.account_id, safe='')}/seasons/lifetime"
        )
        payload = await self._get_json(url, "PUBG lifetime stats")
        stats = (payload.get("data") or {}).get("attributes", {}).get("gameModeStats", {})
        mode, lifetime = self._preferred_mode_stats(stats)
        matches = ((payload.get("data") or {}).get("relationships") or {}).get("matches", {}).get("data") or []
        matches_played = lifetime.get("roundsPlayed") or 0
        wins = lifetime.get("wins") or 0
        kd = lifetime.get("kdr")
        if kd is None:
            losses = max(matches_played - wins, 0)
            kd = round((lifetime.get("kills") or 0) / losses, 2) if losses else float(lifetime.get("kills") or 0)
        return {
            "view": "lifetime",
            "mode": mode,
            "matches": matches_played,
            "wins": wins,
            "top10s": lifetime.get("top10s"),
            "kills": lifetime.get("kills"),
            "kd": kd,
            "damage": lifetime.get("damageDealt"),
            "headshots": lifetime.get("headshotKills"),
            "assists": lifetime.get("assists"),
            "revives": lifetime.get("revives"),
            "longest_kill": lifetime.get("longestKill"),
            "avg_survival_time": lifetime.get("avgSurvivalTime"),
            "recent_match_ids": [item.get("id") for item in matches if item.get("id")],
            "raw": lifetime or payload,
        }

    async def fetch_recent_match_ids(self, account: AccountInfo, limit: int = 5) -> list[str]:
        if not account.account_id:
            raise NotFoundError("PUBG account has no account id")

        url = f"{BASE_URL}/shards/{quote(account.region, safe='')}/players/{quote(account.account_id, safe='')}"
        payload = await self._get_json(url, "PUBG player matches")
        matches = ((payload.get("data") or {}).get("relationships") or {}).get("matches", {}).get("data") or []
        ids = [item.get("id") for item in matches if item.get("id")]
        return ids[:limit]

    async def fetch_match_summary(self, account: AccountInfo, match_id: str) -> dict:
        if not account.account_id:
            raise NotFoundError("PUBG account has no account id")

        url = f"{BASE_URL}/shards/{quote(account.region, safe='')}/matches/{quote(match_id, safe='')}"
        payload = await self._get_json(url, "PUBG match")
        data = payload.get("data") or {}
        included = payload.get("included") or []
        participant = self._match_participant(account.account_id, data, included)
        stats = participant.get("attributes", {}).get("stats", {}) if participant else {}
        return {
            "match_id": match_id,
            "pubg_account_id": account.account_id,
            "platform": account.region,
            "game_mode": data.get("attributes", {}).get("gameMode") or "unknown",
            "played_at": data.get("attributes", {}).get("createdAt") or "",
            "map_name": data.get("attributes", {}).get("mapName"),
            "placement": stats.get("winPlace"),
            "kills": stats.get("kills"),
            "damage": stats.get("damageDealt"),
            "assists": stats.get("assists"),
            "revives": stats.get("revives"),
            "survival_time_seconds": stats.get("timeSurvived"),
        }

    async def fetch_recent_match_summaries(self, account: AccountInfo, limit: int = 5) -> list[dict]:
        match_ids = await self.fetch_recent_match_ids(account, limit=limit)
        return [await self.fetch_match_summary(account, match_id) for match_id in match_ids]

    async def _get_current_season(self, platform: str) -> str:
        key = f"pubg_season_{platform}"
        cached = await db.get_state(key)
        if cached:
            data = json.loads(cached)
            if int(time.time()) - data.get("fetched_at", 0) < SEASON_TTL_SECONDS:
                return data["season_id"]

        url = f"{BASE_URL}/shards/{quote(platform, safe='')}/seasons"
        payload = await self._get_json(url, "PUBG seasons")
        for season in payload.get("data", []):
            if season.get("attributes", {}).get("isCurrentSeason"):
                season_id = season["id"]
                await db.set_state(key, json.dumps({"season_id": season_id, "fetched_at": int(time.time())}))
                return season_id
        raise NotFoundError(f"PUBG current season not found for {platform}")

    async def _get_json(self, url: str, label: str, params: dict[str, str] | None = None) -> dict:
        LOGGER.info("PUBG provider GET %s", label)
        headers = {"Authorization": f"Bearer {self._api_key}", "Accept": "application/vnd.api+json"}
        try:
            response = await self._client.get(url, headers=headers, params=params)
        except httpx.RequestError as error:
            raise upstream_error(label, error) from error
        handle_response(response, label)
        return response.json()

    def _preferred_mode_stats(self, mode_stats: dict) -> tuple[str, dict]:
        for mode in PREFERRED_GAME_MODES:
            stats = mode_stats.get(mode)
            if stats:
                return mode, stats
        for mode, stats in mode_stats.items():
            if stats:
                return mode, stats
        return PREFERRED_GAME_MODES[0], {}

    def _match_participant(self, account_id: str, match: dict, included: Iterable[dict]) -> dict | None:
        roster_ids = {
            item.get("id")
            for item in ((match.get("relationships") or {}).get("rosters", {}) or {}).get("data") or []
            if item.get("id")
        }
        participant_ids: set[str] = set()
        participant_lookup: dict[str, dict] = {}

        for item in included:
            item_id = item.get("id")
            if item.get("type") == "roster" and item_id in roster_ids:
                relationships = (item.get("relationships") or {}).get("participants", {}) or {}
                participant_ids.update(participant.get("id") for participant in relationships.get("data") or [] if participant.get("id"))
            if item_id:
                participant_lookup[item_id] = item

        for participant_id in participant_ids:
            participant = participant_lookup.get(participant_id)
            stats = (participant or {}).get("attributes", {}).get("stats", {})
            if stats.get("playerId") == account_id:
                return participant
        return None


async def prewarm_current_seasons(platforms: list[str]) -> None:
    provider = PubgProvider()
    for platform in platforms:
        try:
            await provider._get_current_season(platform.lower())
        except Exception:
            LOGGER.exception("Failed to prewarm PUBG season for %s", platform)
