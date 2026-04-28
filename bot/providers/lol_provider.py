from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from bot.config import get_settings
from bot.http_client import get_client
from bot.providers import AccountInfo, NotFoundError, RankInfo, handle_response, upstream_error

LOGGER = logging.getLogger(__name__)

REGIONAL_ROUTES = {
    "br1": "americas",
    "la1": "americas",
    "la2": "americas",
    "na1": "americas",
    "eun1": "europe",
    "euw1": "europe",
    "me1": "europe",
    "tr1": "europe",
    "ru": "europe",
    "jp1": "asia",
    "kr": "asia",
    "oc1": "sea",
    "ph2": "sea",
    "sg2": "sea",
    "th2": "sea",
    "tw2": "sea",
    "vn2": "sea",
}


class LolProvider:
    RankInfo = RankInfo

    def __init__(self, client: httpx.AsyncClient | None = None, api_key: str | None = None) -> None:
        self._client = client or get_client()
        self._api_key = api_key or get_settings().riot_api_key

    async def lookup_account(self, name: str, tag: str, region: str = "vn2") -> AccountInfo:
        platform = region.lower()
        regional = REGIONAL_ROUTES.get(platform)
        if regional is None:
            raise NotFoundError(f"Unsupported LoL region: {region}")

        account_url = (
            f"https://{regional}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
            f"{quote(name, safe='')}/{quote(tag, safe='')}"
        )
        account = await self._get_json(account_url, "LoL account")
        puuid = account.get("puuid")
        if not puuid:
            raise NotFoundError("LoL account payload missing puuid")

        summoner_url = f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
        summoner = await self._get_json(summoner_url, "LoL summoner")
        summoner_id = summoner.get("id")
        if not summoner_id:
            raise NotFoundError("LoL summoner payload missing id")

        canonical_name = account.get("gameName") or name
        tag_line = account.get("tagLine") or tag
        return AccountInfo(puuid, summoner_id, None, canonical_name, tag_line, platform)

    async def fetch_rank(self, account: AccountInfo) -> RankInfo:
        if not account.summoner_id:
            raise NotFoundError("LoL account has no summoner id")

        url = (
            f"https://{account.region}.api.riotgames.com/lol/league/v4/entries/by-summoner/"
            f"{account.summoner_id}"
        )
        entries = await self._get_json(url, "LoL rank")
        solo = next((entry for entry in entries if entry.get("queueType") == "RANKED_SOLO_5x5"), None)
        if solo is None:
            return RankInfo(None, None, None, None, None, {"entries": entries})
        return RankInfo(
            solo.get("tier"),
            solo.get("rank"),
            solo.get("leaguePoints"),
            solo.get("wins"),
            solo.get("losses"),
            solo,
        )

    async def _get_json(self, url: str, label: str) -> dict | list:
        LOGGER.info("LoL provider GET %s", label)
        try:
            response = await self._client.get(url, headers={"X-Riot-Token": self._api_key})
        except httpx.RequestError as error:
            raise upstream_error(label, error) from error
        handle_response(response, label)
        return response.json()
