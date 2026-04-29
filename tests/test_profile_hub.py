from types import SimpleNamespace

import pytest

from bot import db
from bot.profile_embeds import make_profile_response
from bot.profile_hub_service import ProfileHubService


class FakeProvider:
    def __init__(self):
        self.ranked_calls = 0
        self.lifetime_calls = 0
        self.metadata_calls = 0
        self.mastery_calls = 0
        self.match_id_calls = 0
        self.batch_match_id_calls = 0
        self.match_summary_calls = 0
        self.fail_after = None

    async def get_current_season(self, _platform):
        return "season-1"

    async def fetch_ranked_view(self, _account, mode="all", season_id=None):
        self.ranked_calls += 1
        return {
            "tier": "GOLD",
            "division": "2",
            "points": 1500,
            "wins": 12,
            "matches": 50,
            "kd": 2.1,
            "damage": 320.0,
            "mode": "squad-fpp",
            "season_id": season_id or "season-1",
        }

    async def fetch_lifetime_view(self, _account, mode="all"):
        self.lifetime_calls += 1
        return {
            "wins": 22,
            "matches": 220,
            "top10s": 90,
            "kd": 1.85,
            "kills": 330,
            "damage": 410.0,
            "headshots": 44,
            "assists": 40,
            "revives": 15,
            "longest_kill": 278.4,
            "avg_survival_time": 1100.0,
        }

    async def fetch_account_metadata(self, account):
        self.metadata_calls += 1
        return {
            "account_id": account.account_id,
            "name": account.canonical_name,
            "platform": account.region,
            "title_id": "pubg",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2026-04-29T00:00:00Z",
        }

    async def fetch_mastery_view(self, _account):
        self.mastery_calls += 1
        return {
            "weapon": {"weapon_count": 4, "top_weapons": [{"name": "AK47", "level": 31, "kills": 80}]},
            "survival": {"level": 18, "tier": "gold"},
        }

    async def fetch_recent_match_ids(self, _account, limit=10):
        self.match_id_calls += 1
        return ["m1", "m2", "m3"][:limit]

    async def fetch_recent_match_ids_batch(self, accounts, limit=10):
        self.batch_match_id_calls += 1
        return {account.account_id: ["m1", "m2", "m3"][:limit] for account in accounts}

    async def fetch_match_summary(self, account, match_id):
        self.match_summary_calls += 1
        if self.fail_after is not None and self.match_summary_calls > self.fail_after:
            raise RuntimeError("boom")
        index = {"m1": 1, "m2": 2, "m3": 3}[match_id]
        return {
            "match_id": match_id,
            "pubg_account_id": account.account_id,
            "platform": account.region,
            "game_mode": "squad-fpp",
            "match_type": "official",
            "played_at": f"2026-04-29T00:0{index}:00Z",
            "placement": index,
            "kills": index + 1,
            "damage": 100.0 * index,
            "assists": 1,
            "revives": 0,
            "survival_time_seconds": 600.0 * index,
        }


@pytest.mark.usefixtures("tmp_db")
async def test_profile_overview_payload_contains_expected_sections_and_reuses_sources():
    service = ProfileHubService(FakeProvider())
    account = SimpleNamespace(account_id="account-1", canonical_name="PlayerOne", region="steam")

    overview = await service.build(account)
    again = await service.build(account)

    assert set(("metadata", "ranked", "lifetime", "mastery", "recent", "analysis")).issubset(overview.keys())
    assert overview["metadata"]["name"] == "PlayerOne"
    assert overview["ranked"]["tier"] == "GOLD"
    assert again["season_id"] == "season-1"
    assert service.provider.ranked_calls == 1
    assert service.provider.lifetime_calls == 1
    assert service.provider.metadata_calls == 1
    assert service.provider.mastery_calls == 1
    assert service.provider.batch_match_id_calls == 1
    assert service.provider.match_id_calls == 0


@pytest.mark.usefixtures("tmp_db")
async def test_profile_recent_reads_from_db_without_recent_api_calls():
    provider = FakeProvider()
    service = ProfileHubService(provider)
    account = SimpleNamespace(account_id="account-1", canonical_name="PlayerOne", region="steam")
    for index in range(20):
        await db.insert_match_summary_if_absent(
            {
                "match_id": f"match-{index}",
                "pubg_account_id": account.account_id,
                "platform": account.region,
                "game_mode": "squad-fpp",
                "match_type": "official",
                "played_at": f"2026-04-29T00:{index:02d}:00Z",
                "placement": (index % 10) + 1,
                "kills": index % 5,
                "damage": float(index * 10),
                "assists": 1,
                "revives": 0,
                "survival_time_seconds": 600.0 + index,
            }
        )
    await db.set_match_cursor(account.account_id, account.region, {"fetched_at": 123})

    payload = await service.build(account)

    assert payload["recent"]["sample_size"] == 20
    assert provider.batch_match_id_calls == 0
    assert provider.match_id_calls == 0
    assert provider.match_summary_calls == 0


@pytest.mark.usefixtures("tmp_db")
async def test_profile_recent_retries_after_partial_cold_fill():
    provider = FakeProvider()
    provider.fail_after = 1
    service = ProfileHubService(provider)
    account = SimpleNamespace(account_id="account-1", canonical_name="PlayerOne", region="steam")

    with pytest.raises(RuntimeError):
        await service._recent_matches(account, 3)

    provider.fail_after = None
    matches = await service._recent_matches(account, 3)

    assert len(matches) == 3
    assert (await db.get_match_cursor(account.account_id, account.region)) is not None


@pytest.mark.usefixtures("tmp_db")
async def test_profile_overview_render_is_single_interactive_page_seed():
    service = ProfileHubService(FakeProvider())
    account = SimpleNamespace(account_id="account-1", canonical_name="PlayerOne", region="steam")

    embeds = make_profile_response(account, await service.build(account))

    assert len(embeds) == 1
    assert embeds[0].title == "Game Thủ: PlayerOne"
    assert embeds[0].color.value > 0
    assert all(len(embed.fields) <= 25 for embed in embeds)
