import pytest

from bot import db
from bot.match_warmer import tick


class FakeWarmerProvider:
    def __init__(self) -> None:
        self.batch_calls = 0
        self.summary_calls = 0
        self.season_calls = 0
        self.ranked_calls = 0
        self.lifetime_calls = 0
        self.mastery_calls = 0
        self.metadata_calls = 0

    async def fetch_recent_match_ids_batch(self, accounts, limit=50):
        self.batch_calls += 1
        return {account.account_id: ["match-1", "match-2", "match-3"][:limit] for account in accounts}

    async def fetch_match_summary(self, account, match_id):
        self.summary_calls += 1
        return {
            "match_id": match_id,
            "pubg_account_id": account.account_id,
            "platform": account.region,
            "game_mode": "squad-fpp",
            "played_at": f"2026-04-29T00:0{self.summary_calls}:00Z",
            "kills": self.summary_calls,
            "damage": 100.0 * self.summary_calls,
            "assists": 1,
            "revives": 0,
            "survival_time_seconds": 600.0 * self.summary_calls,
        }

    async def get_current_season(self, region):
        self.season_calls += 1
        return "division.bro.official.pc-2018-30"

    async def fetch_ranked_view(self, account, *, mode, season_id):
        self.ranked_calls += 1
        return {"mode": mode, "season_id": season_id}

    async def fetch_lifetime_view(self, account, *, mode):
        self.lifetime_calls += 1
        return {"mode": mode}

    async def fetch_mastery_view(self, account):
        self.mastery_calls += 1
        return {"weapons": []}

    async def fetch_account_metadata(self, account):
        self.metadata_calls += 1
        return {"name": "PlayerOne"}


@pytest.mark.usefixtures("tmp_db")
async def test_match_warmer_tick_inserts_rows_and_dedups():
    await db.upsert_pubg_link(1, "account-1", "steam", "PlayerOne")
    provider = FakeWarmerProvider()

    await tick(provider)
    first_rows = await db.list_recent_match_summaries("account-1", "steam", limit=10)
    first_cursor = await db.get_match_cursor("account-1", "steam")

    await tick(provider)
    second_rows = await db.list_recent_match_summaries("account-1", "steam", limit=10)

    assert provider.batch_calls == 2
    assert provider.summary_calls == 3
    assert provider.ranked_calls == 1
    assert provider.lifetime_calls == 1
    assert provider.mastery_calls == 1
    assert provider.metadata_calls == 1
    assert len(first_rows) == 3
    assert len(second_rows) == 3
    assert first_cursor is not None
    assert first_cursor["recent_ready"] is True
    assert first_cursor["full_7d_sync"] is True
