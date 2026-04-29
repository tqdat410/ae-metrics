from pathlib import Path

import aiosqlite
import pytest

from bot import db


@pytest.mark.usefixtures("tmp_db")
async def test_pubg_link_crud_and_list():
    await db.upsert_pubg_link(1, "account-1", "steam", "PlayerOne")
    await db.upsert_pubg_link(2, "account-2", "psn", "PlayerTwo", linked_by_admin_id=99)

    link = await db.get_pubg_link(1)
    assert link is not None
    assert link["canonical_name"] == "PlayerOne"
    assert [row["discord_user_id"] for row in await db.list_pubg_links()] == [1, 2]

    assert await db.delete_pubg_link(1) is True
    assert await db.get_pubg_link(1) is None
    assert await db.delete_pubg_link(1) is False


@pytest.mark.usefixtures("tmp_db")
async def test_cache_cursor_and_match_summary_round_trip():
    await db.set_cache("account-1", "steam", "ranked", {"tier": "Gold", "points": 50})
    cached = await db.get_cache("account-1", "steam", "ranked")
    assert cached is not None
    payload, age = cached
    assert payload["tier"] == "Gold"
    assert age >= 0

    await db.set_match_cursor("account-1", "steam", {"recent_match_ids": ["match-1"]})
    assert await db.get_match_cursor("account-1", "steam") == {"recent_match_ids": ["match-1"]}

    await db.upsert_match_summary(
        {
            "match_id": "match-1",
            "pubg_account_id": "account-1",
            "platform": "steam",
            "game_mode": "squad-fpp",
            "played_at": "2026-04-29T00:00:00Z",
            "map_name": "Erangel",
            "placement": 1,
            "kills": 8,
            "damage": 450.0,
            "assists": 2,
            "revives": 1,
            "survival_time_seconds": 1600.0,
        }
    )
    recent = await db.list_recent_match_summaries("account-1", "steam", limit=1)
    assert recent[0]["match_id"] == "match-1"


@pytest.mark.asyncio
async def test_legacy_schema_migrates_pubg_rows(tmp_path):
    path = Path(tmp_path / "legacy.db")
    async with aiosqlite.connect(path) as conn:
        await conn.executescript(
            """
            CREATE TABLE linked_accounts (
                discord_id INTEGER NOT NULL,
                game TEXT NOT NULL,
                region TEXT NOT NULL,
                game_name TEXT NOT NULL,
                tag_line TEXT,
                puuid TEXT,
                summoner_id TEXT,
                account_id TEXT,
                linked_at INTEGER NOT NULL,
                PRIMARY KEY(discord_id, game)
            );
            CREATE TABLE rank_cache (
                discord_id INTEGER NOT NULL,
                game TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY(discord_id, game)
            );
            CREATE TABLE api_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );
            INSERT INTO linked_accounts VALUES (10, 'lol', 'vn2', 'Ignored', 'TAG', 'p', 's', NULL, 1);
            INSERT INTO linked_accounts VALUES (20, 'pubg', 'steam', 'PubgPlayer', NULL, NULL, NULL, 'pubg-account', 2);
            INSERT INTO rank_cache VALUES (20, 'pubg', '{"tier":"Gold"}', 3);
            """
        )
        await conn.commit()

    await db.init(str(path))
    migrated = await db.get_pubg_link(20)
    cached = await db.get_cache("pubg-account", "steam", "ranked")
    await db.close()

    assert migrated is not None
    assert migrated["canonical_name"] == "PubgPlayer"
    assert cached is not None
    assert cached[0]["tier"] == "Gold"
    assert path.with_suffix(".db.pre-pubg-pivot.bak").exists()
