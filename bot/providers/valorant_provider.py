from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from bot.config import get_settings
from bot.http_client import get_client
from bot.providers import AccountInfo, NotFoundError, RankInfo, handle_response, upstream_error

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://api.henrikdev.xyz"


class ValorantProvider:
    RankInfo = RankInfo

    def __init__(self, client: httpx.AsyncClient | None = None, api_key: str | None = None) -> None:
        self._client = client or get_client()
        self._api_key = api_key or get_settings().henrik_api_key

    async def lookup_account(self, name: str, tag: str, region: str = "ap") -> AccountInfo:
        url = f"{BASE_URL}/valorant/v2/account/{quote(name, safe='')}/{quote(tag, safe='')}"
        payload = await self._get_json(url, "Valorant account")
        data = payload.get("data", payload)
        puuid = data.get("puuid")
        if not puuid:
            raise NotFoundError("Valorant account payload missing puuid")

        canonical_name = data.get("name") or name
        tag_line = data.get("tag") or tag
        account_region = (data.get("region") or region).lower()
        return AccountInfo(puuid, None, None, canonical_name, tag_line, account_region)

    async def fetch_rank(self, account: AccountInfo) -> RankInfo:
        if not account.tag_line:
            raise NotFoundError("Valorant account has no tag line")

        url = (
            f"{BASE_URL}/valorant/v2/mmr/{quote(account.region, safe='')}/"
            f"{quote(account.canonical_name, safe='')}/{quote(account.tag_line, safe='')}"
        )
        payload = await self._get_json(url, "Valorant rank")
        data = payload.get("data", payload)
        return RankInfo(
            data.get("currenttierpatched"),
            None,
            data.get("ranking_in_tier"),
            None,
            None,
            data,
        )

    async def _get_json(self, url: str, label: str) -> dict:
        LOGGER.info("Valorant provider GET %s", label)
        try:
            response = await self._client.get(url, headers={"Authorization": self._api_key})
        except httpx.RequestError as error:
            raise upstream_error(label, error) from error
        handle_response(response, label)
        return response.json()
