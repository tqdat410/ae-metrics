from __future__ import annotations

import json
import logging
import time
from urllib.parse import quote

import httpx

from bot.config import get_settings
from bot.http_client import get_client
from bot.providers import AccountInfo, NotFoundError, RankInfo, handle_response, upstream_error

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://api.pubg.com"
SEASON_TTL_SECONDS = 7 * 24 * 60 * 60


class PubgProvider:
    RankInfo = RankInfo

    def __init__(self, client: httpx.AsyncClient | None = None, api_key: str | None = None) -> None:
        self._client = client or get_client()
        self._api_key = api_key or get_settings().pubg_api_key

    async def lookup_account(self, name: str, tag: str | None = None, region: str = "steam") -> AccountInfo:
        platform = region.lower()
        url = f"{BASE_URL}/shards/{quote(platform, safe='')}/players"
        payload = await self._get_json(url, "PUBG player", params={"filter[playerNames]": name})
        players = payload.get("data") or []
        if not players:
            raise NotFoundError(f"PUBG player not found: {name}")

        player = players[0]
        account_id = player.get("id")
        attributes = player.get("attributes") or {}
        canonical_name = attributes.get("name") or name
        return AccountInfo(None, None, account_id, canonical_name, None, platform)

    async def fetch_rank(self, account: AccountInfo) -> RankInfo:
        if not account.account_id:
            raise NotFoundError("PUBG account has no account id")

        season_id = await self._get_current_season(account.region)
        url = (
            f"{BASE_URL}/shards/{quote(account.region, safe='')}/players/"
            f"{quote(account.account_id, safe='')}/seasons/{quote(season_id, safe='')}/ranked"
        )
        payload = await self._get_json(url, "PUBG rank")
        stats = (payload.get("data") or {}).get("attributes", {}).get("rankedGameModeStats", {})
        ranked = stats.get("squad-fpp") or stats.get("squad") or stats.get("duo-fpp") or stats.get("solo-fpp") or {}
        tier = ranked.get("currentTier") or {}
        return RankInfo(
            tier.get("tier"),
            tier.get("subTier"),
            ranked.get("currentRankPoint"),
            ranked.get("roundsWon"),
            None,
            ranked or payload,
        )

    async def _get_current_season(self, platform: str) -> str:
        from bot import db

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


async def prewarm_current_seasons(platforms: list[str]) -> None:
    provider = PubgProvider()
    for platform in platforms:
        try:
            await provider._get_current_season(platform.lower())
        except Exception:
            LOGGER.exception("Failed to prewarm PUBG season for %s", platform)
