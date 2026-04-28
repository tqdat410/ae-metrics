import pytest

from bot import db


@pytest.mark.usefixtures("tmp_db")
async def test_link_crud_and_game_filter():
    await db.upsert_link(1, "lol", "vn2", "Player", "VN2", "p", "s", None)
    await db.upsert_link(2, "pubg", "steam", "PubgPlayer", None, None, None, "acc")

    link = await db.get_link(1, "lol")
    assert link is not None
    assert link["summoner_id"] == "s"
    assert [row["discord_id"] for row in await db.list_links_by_game("lol")] == [1]

    assert await db.delete_link(1, "lol") is True
    assert await db.get_link(1, "lol") is None
    assert await db.delete_link(1, "lol") is False


@pytest.mark.usefixtures("tmp_db")
async def test_cache_round_trip_and_delete():
    await db.set_cache(1, "valo", {"tier": "Gold", "points": 50})
    cached = await db.get_cache(1, "valo")
    assert cached is not None
    payload, age = cached
    assert payload["tier"] == "Gold"
    assert age >= 0

    await db.delete_cache(1, "valo")
    assert await db.get_cache(1, "valo") is None

