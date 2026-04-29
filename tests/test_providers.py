import httpx
import pytest

from bot.providers import ApiKeyError, NotFoundError, RateLimitError, UpstreamError, handle_response
from bot.providers.pubg_provider import PubgProvider


@pytest.mark.parametrize(
    ("status", "error_type"),
    [(404, NotFoundError), (429, RateLimitError), (401, ApiKeyError), (403, ApiKeyError), (500, UpstreamError)],
)
def test_handle_response_maps_errors(status, error_type):
    response = httpx.Response(status, request=httpx.Request("GET", "https://example.test"))
    with pytest.raises(error_type):
        handle_response(response, "service")


@pytest.mark.usefixtures("tmp_db")
async def test_pubg_provider_parses_ranked_and_lifetime_views(respx_mock):
    provider = PubgProvider(client=httpx.AsyncClient(), api_key="test")
    account = type("Account", (), {"account_id": "acc-1", "canonical_name": "Player", "region": "steam"})()

    respx_mock.get("https://api.pubg.com/shards/steam/seasons").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "season-1", "attributes": {"isCurrentSeason": True}}]},
        )
    )
    respx_mock.get("https://api.pubg.com/shards/steam/players/acc-1/seasons/season-1/ranked").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "attributes": {
                        "rankedGameModeStats": {
                            "squad-fpp": {
                                "currentTier": {"tier": "GOLD", "subTier": "2"},
                                "currentRankPoint": 1500,
                                "roundsWon": 12,
                                "roundsPlayed": 50,
                                "kills": 99,
                                "kdr": 2.1,
                                "damageDealt": 12345.0,
                            }
                        }
                    }
                }
            },
        )
    )
    respx_mock.get("https://api.pubg.com/shards/steam/players/acc-1/seasons/lifetime").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "attributes": {
                        "gameModeStats": {
                            "squad-fpp": {
                                "roundsPlayed": 200,
                                "wins": 20,
                                "top10s": 80,
                                "kills": 300,
                                "kdr": 1.8,
                                "damageDealt": 50000,
                                "headshotKills": 40,
                                "assists": 75,
                                "revives": 60,
                            }
                        }
                    },
                    "relationships": {"matches": {"data": [{"id": "match-1"}, {"id": "match-2"}]}},
                }
            },
        )
    )

    ranked = await provider.fetch_ranked_view(account)
    lifetime = await provider.fetch_lifetime_view(account)
    await provider._client.aclose()

    assert ranked["tier"] == "GOLD"
    assert ranked["points"] == 1500
    assert lifetime["matches"] == 200
    assert lifetime["recent_match_ids"] == ["match-1", "match-2"]


async def test_pubg_provider_fetch_match_summary(respx_mock):
    provider = PubgProvider(client=httpx.AsyncClient(), api_key="test")
    account = type("Account", (), {"account_id": "acc-1", "canonical_name": "Player", "region": "steam"})()
    respx_mock.get("https://api.pubg.com/shards/steam/matches/match-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "attributes": {"gameMode": "squad-fpp", "createdAt": "2026-04-29T00:00:00Z", "mapName": "Erangel"},
                    "relationships": {"rosters": {"data": [{"id": "roster-1"}]}},
                },
                "included": [
                    {
                        "id": "roster-1",
                        "type": "roster",
                        "relationships": {"participants": {"data": [{"id": "participant-1"}]}},
                    },
                    {
                        "id": "participant-1",
                        "type": "participant",
                        "attributes": {
                            "stats": {
                                "playerId": "acc-1",
                                "winPlace": 3,
                                "kills": 5,
                                "damageDealt": 320.5,
                                "assists": 1,
                                "revives": 0,
                                "timeSurvived": 1200.0,
                            }
                        },
                    },
                ],
            },
        )
    )

    summary = await provider.fetch_match_summary(account, "match-1")
    await provider._client.aclose()

    assert summary["match_id"] == "match-1"
    assert summary["placement"] == 3
    assert summary["kills"] == 5


async def test_pubg_provider_rejects_missing_account_id_in_lookup(respx_mock):
    provider = PubgProvider(client=httpx.AsyncClient(), api_key="test")
    respx_mock.get("https://api.pubg.com/shards/steam/players").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": None, "attributes": {"name": "Player"}}]},
        )
    )

    with pytest.raises(UpstreamError):
        await provider.lookup_account("Player", None, "steam")
    await provider._client.aclose()
