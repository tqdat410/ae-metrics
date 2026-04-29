from datetime import datetime, timedelta, timezone

import pytest

from bot import db


@pytest.mark.usefixtures("tmp_db")
async def test_insert_match_summary_if_absent_keeps_first_row():
    summary = {
        "match_id": "match-1",
        "pubg_account_id": "account-1",
        "platform": "steam",
        "game_mode": "squad-fpp",
        "played_at": "2026-04-29T00:00:00Z",
        "kills": 2,
        "damage": 100.0,
        "assists": 1,
        "revives": 0,
        "survival_time_seconds": 1200,
    }
    await db.insert_match_summary_if_absent(summary)
    before = await db.list_recent_match_summaries("account-1", "steam", limit=1)

    summary["kills"] = 99
    await db.insert_match_summary_if_absent(summary)
    after = await db.list_recent_match_summaries("account-1", "steam", limit=1)

    assert before == after
    assert after[0]["kills"] == 2


@pytest.mark.usefixtures("tmp_db")
async def test_insert_match_summary_if_absent_is_scoped_per_account():
    base = {
        "match_id": "shared-match",
        "platform": "steam",
        "game_mode": "squad-fpp",
        "played_at": "2026-04-29T00:00:00Z",
        "kills": 2,
        "damage": 100.0,
        "assists": 1,
        "revives": 0,
        "survival_time_seconds": 1200,
    }
    await db.insert_match_summary_if_absent({**base, "pubg_account_id": "account-1"})
    await db.insert_match_summary_if_absent({**base, "pubg_account_id": "account-2", "kills": 5})

    first = await db.list_recent_match_summaries("account-1", "steam", limit=5)
    second = await db.list_recent_match_summaries("account-2", "steam", limit=5)

    assert first[0]["kills"] == 2
    assert second[0]["kills"] == 5


@pytest.mark.usefixtures("tmp_db")
async def test_list_match_activity_since_unix_filters_numeric_window():
    now = datetime.now(timezone.utc)
    offsets = [1, 3, 7 - (1 / 1440), 7 + (1 / 1440), 10]
    for index, days in enumerate(offsets, start=1):
        played_at = now - timedelta(days=days)
        await db.insert_match_summary_if_absent(
            {
                "match_id": f"match-{index}",
                "pubg_account_id": "account-1",
                "platform": "steam",
                "game_mode": "squad-fpp",
                "played_at": played_at.isoformat().replace("+00:00", "Z"),
                "kills": 1,
                "damage": 50.0,
                "assists": 0,
                "revives": 0,
                "survival_time_seconds": 600,
            }
        )

    rows = await db.list_match_activity_since_unix(int((now - timedelta(days=7)).timestamp()))

    assert rows == [
        {
            "pubg_account_id": "account-1",
            "platform": "steam",
            "match_count": 3,
            "total_survival_seconds": 1800.0,
        }
    ]


@pytest.mark.usefixtures("tmp_db")
async def test_delete_pubg_link_purges_related_rows():
    await db.upsert_pubg_link(1, "account-1", "steam", "PlayerOne")
    await db.insert_match_summary_if_absent(
        {
            "match_id": "match-1",
            "pubg_account_id": "account-1",
            "platform": "steam",
            "game_mode": "squad-fpp",
            "played_at": "2026-04-29T00:00:00Z",
            "kills": 2,
            "damage": 100.0,
            "assists": 1,
            "revives": 0,
            "survival_time_seconds": 1200,
        }
    )
    await db.set_match_cursor("account-1", "steam", {"fetched_at": 123})
    await db.upsert_stat_snapshot("account-1", "steam", "ranked", "2026-04-29", {"tier": "gold"})

    deleted = await db.delete_pubg_link(1)

    assert deleted is True
    assert await db.get_pubg_link(1) is None
    assert await db.get_match_cursor("account-1", "steam") is None
    assert await db.list_recent_match_summaries("account-1", "steam", limit=5) == []
