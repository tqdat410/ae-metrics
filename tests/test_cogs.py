from types import SimpleNamespace

import pytest

from bot import db
from bot.cogs.admin_cog import AdminCog
from bot.cogs.leaderboard_cog import LeaderboardCog
from bot.cogs.link_cog import LinkCog
from bot.cogs.stats_cog import StatsCog


class FakeResponse:
    def __init__(self):
        self.calls = []

    async def defer(self, *, ephemeral=False):
        self.calls.append(ephemeral)


class FakeFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, *, embed, ephemeral=False):
        self.messages.append({"embed": embed, "ephemeral": ephemeral})


class FakeInteraction:
    def __init__(self, user_id: int, *, admin_id: int | None = None, administrator: bool = False):
        self.user = SimpleNamespace(
            id=user_id,
            mention=f"<@{user_id}>",
            guild_permissions=SimpleNamespace(administrator=administrator),
        )
        self.client = SimpleNamespace(settings=SimpleNamespace(admin_discord_id=admin_id))
        self.response = FakeResponse()
        self.followup = FakeFollowup()


@pytest.mark.usefixtures("tmp_db")
async def test_unlink_is_ephemeral():
    await db.upsert_pubg_link(1, "account-1", "steam", "PlayerOne")
    cog = LinkCog(SimpleNamespace())
    interaction = FakeInteraction(1)

    await cog.unlink.callback(cog, interaction)

    assert interaction.response.calls == [True]
    assert interaction.followup.messages[-1]["ephemeral"] is True


async def test_admin_link_delete_rejects_non_admin():
    cog = AdminCog(SimpleNamespace())
    interaction = FakeInteraction(1, admin_id=99, administrator=False)
    target = SimpleNamespace(id=2, mention="<@2>")

    await cog.link_delete.callback(cog, interaction, target)

    assert interaction.response.calls == [True]
    assert interaction.followup.messages[-1]["ephemeral"] is True
    assert interaction.followup.messages[-1]["embed"].title == "Not allowed"


async def test_admin_link_set_sanitizes_errors(monkeypatch):
    class BrokenProvider:
        async def lookup_account(self, name, tag, platform):
            raise RuntimeError("internal secret")

    monkeypatch.setattr("bot.cogs.admin_cog.get_provider", lambda: BrokenProvider())
    cog = AdminCog(SimpleNamespace())
    interaction = FakeInteraction(99, admin_id=99)
    target = SimpleNamespace(id=2, mention="<@2>")

    await cog.link_set.callback(cog, interaction, target, "Player", "steam")

    message = interaction.followup.messages[-1]["embed"].description
    assert "internal secret" not in message


@pytest.mark.usefixtures("tmp_db")
async def test_leaderboard_is_public(monkeypatch):
    await db.upsert_pubg_link(1, "account-1", "steam", "PlayerOne")
    cog = LeaderboardCog(SimpleNamespace())
    interaction = FakeInteraction(1)

    async def fake_entries(metric, rows):
        assert metric == "rank_points"
        assert rows
        return ["**1.** <@1> - `PlayerOne` - GOLD 2 - 1500 pts"]

    monkeypatch.setattr(cog, "_entries", fake_entries)

    await cog.leaderboard.callback(cog, interaction, "rank_points")

    assert interaction.response.calls == [False]
    assert interaction.followup.messages[-1]["ephemeral"] is False


async def test_profile_payload_only_snapshots_fresh_fetch(monkeypatch):
    cog = StatsCog(SimpleNamespace())
    account = SimpleNamespace(account_id="account-1", region="steam")
    snapshot_calls = []

    async def no_wait(_name):
        return None

    async def cached_view(*_args, **_kwargs):
        return {"tier": "GOLD"}, False

    async def snapshot(*args):
        snapshot_calls.append(args)

    monkeypatch.setattr("bot.cogs.stats_cog.throttle", no_wait)
    monkeypatch.setattr("bot.cogs.stats_cog.cache.get_or_fetch_view", cached_view)
    monkeypatch.setattr("bot.cogs.stats_cog.db.upsert_stat_snapshot", snapshot)

    payload = await cog._profile_payload(account, "ranked")

    assert payload["tier"] == "GOLD"
    assert snapshot_calls == []
