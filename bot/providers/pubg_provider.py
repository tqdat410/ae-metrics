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
from bot.rate_limiter import throttle

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

    async def fetch_account_metadata(self, account: AccountInfo) -> dict:
        if not account.account_id:
            raise NotFoundError("PUBG account has no account id")
        url = f"{BASE_URL}/shards/{quote(account.region, safe='')}/players/{quote(account.account_id, safe='')}"
        payload = await self._get_json(url, "PUBG player metadata")
        data = payload.get("data") or {}
        attributes = data.get("attributes") or {}
        clan_data = (((data.get("relationships") or {}).get("clan") or {}).get("data") or {})
        return {
            "account_id": data.get("id") or account.account_id,
            "name": attributes.get("name") or account.canonical_name,
            "platform": account.region,
            "clan_id": clan_data.get("id"),
            "title_id": attributes.get("titleId"),
            "shard_id": attributes.get("shardId"),
            "patch_version": attributes.get("patchVersion"),
            "created_at": attributes.get("createdAt"),
            "updated_at": attributes.get("updatedAt"),
        }

    async def get_current_season(self, platform: str) -> str:
        return await self._get_current_season(platform)

    async def fetch_ranked_view(self, account: AccountInfo, mode: str = "all", season_id: str | None = None) -> dict:
        if not account.account_id:
            raise NotFoundError("PUBG account has no account id")

        current_season = season_id or await self._get_current_season(account.region)
        url = (
            f"{BASE_URL}/shards/{quote(account.region, safe='')}/players/"
            f"{quote(account.account_id, safe='')}/seasons/{quote(current_season, safe='')}/ranked"
        )
        payload = await self._get_json(url, "PUBG ranked stats")
        stats = (payload.get("data") or {}).get("attributes", {}).get("rankedGameModeStats", {})
        selected_mode, ranked = self._mode_stats(stats, mode)
        tier = ranked.get("currentTier") or {}
        return {
            "view": "ranked",
            "requested_mode": mode,
            "mode": selected_mode,
            "season_id": current_season,
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
            "modes": self._normalize_modes(stats, ranked=True),
            "raw": ranked or payload,
        }

    async def fetch_lifetime_view(self, account: AccountInfo, mode: str = "all") -> dict:
        if not account.account_id:
            raise NotFoundError("PUBG account has no account id")

        url = (
            f"{BASE_URL}/shards/{quote(account.region, safe='')}/players/"
            f"{quote(account.account_id, safe='')}/seasons/lifetime"
        )
        payload = await self._get_json(url, "PUBG lifetime stats")
        stats = (payload.get("data") or {}).get("attributes", {}).get("gameModeStats", {})
        selected_mode, lifetime = self._mode_stats(stats, mode)
        matches = ((payload.get("data") or {}).get("relationships") or {}).get("matches", {}).get("data") or []
        matches_played = lifetime.get("roundsPlayed") or 0
        wins = lifetime.get("wins") or 0
        kd = lifetime.get("kdr")
        if kd is None:
            losses = max(matches_played - wins, 0)
            kd = round((lifetime.get("kills") or 0) / losses, 2) if losses else float(lifetime.get("kills") or 0)
        return {
            "view": "lifetime",
            "requested_mode": mode,
            "mode": selected_mode,
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
            "modes": self._normalize_modes(stats, ranked=False),
            "raw": lifetime or payload,
        }

    async def fetch_weapon_mastery(self, account: AccountInfo) -> dict:
        if not account.account_id:
            raise NotFoundError("PUBG account has no account id")
        url = f"{BASE_URL}/shards/{quote(account.region, safe='')}/players/{quote(account.account_id, safe='')}/weapon_mastery"
        payload = await self._get_json(url, "PUBG weapon mastery")
        attributes = (payload.get("data") or {}).get("attributes") or {}
        summary = (attributes.get("weaponMasterySummary") or {}).get("weaponSummaries") or {}
        top_weapons = []
        for weapon_name, weapon_stats in summary.items():
            totals = self._weapon_totals(weapon_stats)
            top_weapons.append(
                {
                    "name": weapon_name.replace("Item_Weapon_", "").replace("_C", ""),
                    "level": weapon_stats.get("LevelCurrent") or weapon_stats.get("levelCurrent") or 0,
                    "tier": weapon_stats.get("TierCurrent") or weapon_stats.get("tierCurrent"),
                    "xp_total": totals.get("xpTotal"),
                    "kills": totals.get("kills"),
                    "defeats": totals.get("defeats"),
                    "headshots": totals.get("headshots"),
                }
            )
        top_weapons.sort(key=lambda item: (item.get("kills") or 0, item.get("defeats") or 0, item.get("level") or 0), reverse=True)
        return {"top_weapons": top_weapons[:3], "weapon_count": len(summary), "raw": attributes or payload}

    async def fetch_survival_mastery(self, account: AccountInfo) -> dict:
        if not account.account_id:
            raise NotFoundError("PUBG account has no account id")
        url = f"{BASE_URL}/shards/{quote(account.region, safe='')}/players/{quote(account.account_id, safe='')}/survival_mastery"
        payload = await self._get_json(url, "PUBG survival mastery")
        attributes = (payload.get("data") or {}).get("attributes") or {}
        return {
            "level": attributes.get("survivalMasteryLevel") or attributes.get("level") or 0,
            "xp": attributes.get("totalXp") or attributes.get("xp") or 0,
            "tier": attributes.get("tier"),
            "raw": attributes or payload,
        }

    async def fetch_mastery_view(self, account: AccountInfo) -> dict:
        weapon = await self.fetch_weapon_mastery(account)
        survival = await self.fetch_survival_mastery(account)
        return {"weapon": weapon, "survival": survival}

    async def fetch_recent_match_ids(self, account: AccountInfo, limit: int | None = 5) -> list[str]:
        if not account.account_id:
            raise NotFoundError("PUBG account has no account id")

        url = f"{BASE_URL}/shards/{quote(account.region, safe='')}/players/{quote(account.account_id, safe='')}"
        payload = await self._get_json(url, "PUBG player matches")
        matches = ((payload.get("data") or {}).get("relationships") or {}).get("matches", {}).get("data") or []
        ids = [item.get("id") for item in matches if item.get("id")]
        return ids if limit is None else ids[:limit]

    async def fetch_recent_match_ids_batch(self, accounts: Iterable[AccountInfo], limit: int | None = 10) -> dict[str, list[str]]:
        account_list = [account for account in accounts if account.account_id]
        if not account_list:
            return {}

        platform = account_list[0].region
        if any(account.region != platform for account in account_list):
            raise ValueError("Batch recent-match fetch requires accounts from the same platform")

        account_ids = [account.account_id for account in account_list if account.account_id]
        url = f"{BASE_URL}/shards/{quote(platform, safe='')}/players"
        payload = await self._get_json(
            url,
            "PUBG player matches batch",
            params={"filter[playerIds]": ",".join(account_ids)},
        )
        players = payload.get("data") or []
        recent_ids: dict[str, list[str]] = {account_id: [] for account_id in account_ids}
        returned_ids: set[str] = set()
        for player in players:
            account_id = player.get("id")
            if not account_id:
                continue
            returned_ids.add(account_id)
            matches = ((player.get("relationships") or {}).get("matches") or {}).get("data") or []
            ids = [item.get("id") for item in matches if item.get("id")]
            recent_ids[account_id] = ids if limit is None else ids[:limit]
        missing_ids = sorted(set(account_ids) - returned_ids)
        for account_id in missing_ids:
            LOGGER.warning("PUBG player missing from batch matches response: account_id=%s platform=%s", account_id, platform)
        return recent_ids

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
            "match_type": data.get("attributes", {}).get("matchType"),
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
        await throttle("pubg")
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

    def _mode_stats(self, mode_stats: dict, requested_mode: str) -> tuple[str, dict]:
        normalized = (requested_mode or "all").lower()
        if normalized in {"all", "ranked"}:
            return self._preferred_mode_stats(mode_stats)
        return normalized, mode_stats.get(normalized) or {}

    def _normalize_modes(self, mode_stats: dict, *, ranked: bool) -> dict[str, dict]:
        normalized: dict[str, dict] = {}
        for mode, stats in mode_stats.items():
            if not stats:
                continue
            normalized[mode] = {
                "matches": stats.get("roundsPlayed"),
                "wins": stats.get("roundsWon" if ranked else "wins"),
                "kills": stats.get("kills"),
                "kd": stats.get("kdr"),
                "damage": stats.get("damageDealt"),
            }
        return normalized

    def _weapon_totals(self, weapon_stats: dict) -> dict:
        for key in ("OfficialStatsTotal", "CompetitiveStatsTotal", "StatsTotal"):
            totals = weapon_stats.get(key)
            if totals:
                return totals
        return {}

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
