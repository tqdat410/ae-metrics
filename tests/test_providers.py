import httpx
import pytest

from bot.providers import ApiKeyError, NotFoundError, RateLimitError, UpstreamError, handle_response
from bot.providers.lol_provider import REGIONAL_ROUTES, LolProvider
from bot.providers.valorant_provider import ValorantProvider


@pytest.mark.parametrize(
    ("status", "error_type"),
    [(404, NotFoundError), (429, RateLimitError), (401, ApiKeyError), (403, ApiKeyError), (500, UpstreamError)],
)
def test_handle_response_maps_errors(status, error_type):
    response = httpx.Response(status, request=httpx.Request("GET", "https://example.test"))
    with pytest.raises(error_type):
        handle_response(response, "service")


def test_lol_region_routing_includes_vietnam_and_common_regions():
    assert REGIONAL_ROUTES["vn2"] == "sea"
    assert REGIONAL_ROUTES["na1"] == "americas"
    assert REGIONAL_ROUTES["euw1"] == "europe"
    assert REGIONAL_ROUTES["kr"] == "asia"


@pytest.mark.usefixtures("tmp_db")
async def test_lol_provider_raises_for_unknown_region():
    provider = LolProvider(client=httpx.AsyncClient(), api_key="test")
    with pytest.raises(NotFoundError):
        await provider.lookup_account("Name", "TAG", "unknown")
    await provider._client.aclose()


async def test_valorant_rank_does_not_treat_mmr_delta_as_wins(respx_mock):
    provider = ValorantProvider(client=httpx.AsyncClient(), api_key="test")
    account = type("Account", (), {"region": "ap", "canonical_name": "Player", "tag_line": "VN2"})()
    respx_mock.get("https://api.henrikdev.xyz/valorant/v2/mmr/ap/Player/VN2").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"currenttierpatched": "Gold 2", "ranking_in_tier": 55, "elo_change_to_last_game": 25}},
        )
    )

    rank = await provider.fetch_rank(account)

    assert rank.tier == "Gold 2"
    assert rank.points == 55
    assert rank.wins is None
    assert rank.losses is None
    await provider._client.aclose()
