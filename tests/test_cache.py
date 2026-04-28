from dataclasses import dataclass

import pytest

from bot import cache, db


@dataclass
class FakeRank:
    tier: str
    division: str | None
    points: int
    wins: int | None = None
    losses: int | None = None
    raw: dict | None = None


class FakeProvider:
    RankInfo = FakeRank

    def __init__(self):
        self.calls = 0

    async def fetch_rank(self, account):
        self.calls += 1
        return FakeRank("GOLD", "II", 44, raw={})


@pytest.mark.usefixtures("tmp_db")
async def test_get_or_fetch_rank_caches_result():
    provider = FakeProvider()
    first = await cache.get_or_fetch_rank(1, "lol", object(), provider)
    second = await cache.get_or_fetch_rank(1, "lol", object(), provider)

    assert first.tier == "GOLD"
    assert second.tier == "GOLD"
    assert provider.calls == 1


@pytest.mark.usefixtures("tmp_db")
async def test_invalidate_deletes_cache():
    await db.set_cache(1, "lol", {"tier": "SILVER", "division": "I", "points": 1})
    await cache.invalidate(1, "lol")
    assert await db.get_cache(1, "lol") is None

