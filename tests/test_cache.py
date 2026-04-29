import pytest

from bot import cache, db


class FakeProvider:
    def __init__(self):
        self.calls = 0

    async def ranked(self):
        self.calls += 1
        return {"tier": "GOLD", "division": "II", "points": 44}


@pytest.mark.usefixtures("tmp_db")
async def test_get_or_fetch_view_caches_result():
    provider = FakeProvider()
    first, first_fetched = await cache.get_or_fetch_view("account-1", "steam", "ranked", provider.ranked)
    second, second_fetched = await cache.get_or_fetch_view("account-1", "steam", "ranked", provider.ranked)

    assert first["tier"] == "GOLD"
    assert second["points"] == 44
    assert first_fetched is True
    assert second_fetched is False
    assert provider.calls == 1


@pytest.mark.usefixtures("tmp_db")
async def test_invalidate_deletes_cached_view():
    await db.set_cache("account-1", "steam", "ranked", {"tier": "SILVER", "division": "I", "points": 1})
    await cache.invalidate("account-1", "steam", "ranked")
    assert await db.get_cache("account-1", "steam", "ranked") is None
