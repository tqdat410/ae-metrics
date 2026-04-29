from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import httpx


@dataclass(frozen=True)
class AccountInfo:
    puuid: str | None
    summoner_id: str | None
    account_id: str | None
    canonical_name: str
    tag_line: str | None
    region: str


@dataclass(frozen=True)
class RankInfo:
    tier: str | None
    division: str | None
    points: int | None
    wins: int | None
    losses: int | None
    raw: dict[str, Any] = field(default_factory=dict)


class ProviderError(Exception):
    """Base class for provider failures safe to show in bot responses."""


class NotFoundError(ProviderError):
    pass


class RateLimitError(ProviderError):
    pass


class ApiKeyError(ProviderError):
    pass


class UpstreamError(ProviderError):
    pass


def handle_response(response: httpx.Response, service: str) -> None:
    status = response.status_code
    if status < 400:
        return
    if status == 404:
        raise NotFoundError(f"{service} account or stats not found")
    if status == 429:
        raise RateLimitError(f"{service} rate limit exceeded")
    if status in {401, 403}:
        raise ApiKeyError(f"{service} API key rejected")
    if status >= 500:
        raise UpstreamError(f"{service} upstream returned {status}")
    raise ProviderError(f"{service} request failed with HTTP {status}")


def upstream_error(service: str, error: httpx.RequestError) -> UpstreamError:
    return UpstreamError(f"{service} request failed: {error.__class__.__name__}")


def account_from_link(link: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        account_id=link["pubg_account_id"],
        canonical_name=link["canonical_name"],
        region=link["platform"],
    )


def get_provider():
    from bot.providers.pubg_provider import PubgProvider

    return PubgProvider()
