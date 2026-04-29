from types import SimpleNamespace

import pytest

from bot import db
from bot.compare_view import CompareView
from bot.profile_view import ProfileView
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

    async def send(self, *, content=None, embed=None, embeds=None, view=None, ephemeral=False, wait=False):
        message = {"content": content, "embed": embed, "embeds": embeds, "view": view, "ephemeral": ephemeral, "wait": wait}
        self.messages.append(message)
        async def edit(**kwargs):
            message["edit"] = kwargs
            return None
        return SimpleNamespace(edit=edit, **message)


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

    async def fake_refresh(rows):
        assert rows

    async def fake_entries(rows):
        assert rows
        return ["`[#1]` **PlayerOne** :: `2.5h | 3 matches`"]

    monkeypatch.setattr(cog, "_refresh_recent_matches", fake_refresh)
    monkeypatch.setattr(cog, "_entries", fake_entries)

    await cog.leaderboard.callback(cog, interaction)

    assert interaction.response.calls == [False]
    assert interaction.followup.messages[-1]["ephemeral"] is False
    assert interaction.followup.messages[-1]["view"] is None


@pytest.mark.usefixtures("tmp_db")
async def test_compare_sends_one_embed_with_view(monkeypatch):
    await db.upsert_pubg_link(1, "account-1", "steam", "PlayerOne")
    await db.upsert_pubg_link(2, "account-2", "steam", "PlayerTwo")
    cog = StatsCog(SimpleNamespace())
    interaction = FakeInteraction(1)
    user_a = SimpleNamespace(id=1, display_name="Alpha", mention="<@1>")
    user_b = SimpleNamespace(id=2, display_name="Bravo", mention="<@2>")

    async def fake_build(account):
        return {
            "view": "overview",
            "generated_at": "2026-04-29T00:00:00+00:00",
            "metadata": {"name": account.canonical_name, "platform": account.region},
            "ranked": {"tier": "GOLD", "division": "2", "points": 1500, "wins": 10, "matches": 40, "kd": 2.0, "mode": "squad-fpp"},
            "lifetime": {"wins": 20, "matches": 200, "top10s": 90, "kd": 1.8, "kills": 250, "damage": 40000.0, "headshots": 20, "assists": 30, "revives": 10, "longest_kill": 200.0, "avg_survival_time": 900.0},
            "recent": {"sample_size": 20, "wins": 2, "avg_placement": 4.5, "avg_kills": 3.0, "avg_damage": 250.0, "top10_rate": 50.0, "avg_survival_time_seconds": 1000.0, "matches": []},
        }

    monkeypatch.setattr(cog.profile_hub, "build", fake_build)

    await cog.compare.callback(cog, interaction, user_a, user_b)

    message = interaction.followup.messages[-1]
    assert interaction.response.calls == [True]
    assert message["ephemeral"] is True
    assert isinstance(message["view"], CompareView)
    assert message["embed"] is not None
    assert message["embeds"] is None
    assert message["wait"] is True


def test_compare_command_has_no_view_option():
    option_names = [param.name for param in StatsCog.compare.parameters]
    assert option_names == ["user_a", "user_b"]


def test_matches_command_is_not_registered():
    command_names = {command.name for command in StatsCog.__cog_app_commands__}
    assert "matches" not in command_names


@pytest.mark.usefixtures("tmp_db")
async def test_profile_sends_one_embed_with_view(monkeypatch):
    await db.upsert_pubg_link(1, "account-1", "steam", "PlayerOne")
    cog = StatsCog(SimpleNamespace())
    interaction = FakeInteraction(1)

    async def fake_build(account):
        assert account.account_id == "account-1"
        return {
            "view": "overview",
            "season_id": "season-1",
            "generated_at": "2026-04-29T00:00:00+00:00",
            "metadata": {"account_id": "account-1", "name": "PlayerOne", "platform": "steam", "title_id": "pubg"},
            "ranked": {"tier": "GOLD", "division": "2", "points": 1500, "wins": 10, "matches": 40, "kd": 2.0, "damage": 300.0, "mode": "squad-fpp"},
            "lifetime": {"wins": 20, "matches": 200, "top10s": 90, "kd": 1.8, "kills": 250, "damage": 400.0, "headshots": 20, "assists": 30, "revives": 10, "longest_kill": 200.0, "avg_survival_time": 900.0},
            "recent": {"sample_size": 2, "avg_placement": 4.5, "avg_kills": 3.0, "avg_damage": 250.0, "top10_rate": 50.0, "matches": []},
            "mastery": {"weapon": {"weapon_count": 4, "top_weapons": [{"name": "AK47", "level": 31, "kills": 80}]}, "survival": {"level": 18}},
            "analysis": {"form": "Stable form."},
        }

    monkeypatch.setattr(cog.profile_hub, "build", fake_build)

    await cog.profile.callback(cog, interaction)

    message = interaction.followup.messages[-1]
    assert interaction.response.calls == [True]
    assert isinstance(message["view"], ProfileView)
    assert message["embed"] is not None
    assert message["embeds"] is None
    assert message["content"] is None


async def test_lookup_sends_overview_embed(monkeypatch):
    cog = StatsCog(SimpleNamespace())
    interaction = FakeInteraction(1)

    async def lookup_account(name, tag, platform):
        assert name == "PlayerOne"
        assert tag is None
        assert platform == "steam"
        return SimpleNamespace(account_id="account-1", canonical_name="PlayerOne", region="steam")

    async def fake_build(_account):
        return {
            "view": "overview",
            "generated_at": "2026-04-29T00:00:00+00:00",
            "season_id": "season-1",
            "metadata": {"account_id": "account-1", "name": "PlayerOne", "platform": "steam"},
            "ranked": {"tier": "GOLD", "division": "2", "points": 1500, "wins": 10, "matches": 40, "kd": 2.0, "damage": 300.0, "mode": "squad-fpp"},
            "lifetime": {"wins": 20, "matches": 200, "top10s": 90, "kd": 1.8, "kills": 250, "damage": 400.0, "headshots": 20, "assists": 30, "revives": 10, "longest_kill": 200.0, "avg_survival_time": 900.0},
            "recent": {"sample_size": 2, "avg_placement": 4.5, "avg_kills": 3.0, "avg_damage": 250.0, "top10_rate": 50.0, "avg_survival_time_seconds": 1000.0, "matches": []},
            "mastery": {"weapon": {"weapon_count": 4, "top_weapons": [{"name": "AK47", "level": 31, "kills": 80}]}, "survival": {"level": 18}},
            "analysis": {"form": "Stable form."},
        }

    monkeypatch.setattr(cog.provider, "lookup_account", lookup_account)
    monkeypatch.setattr(cog.profile_hub, "build", fake_build)

    await cog.lookup.callback(cog, interaction, "PlayerOne", "steam")

    message = interaction.followup.messages[-1]
    assert isinstance(message["view"], ProfileView)
    assert message["embed"] is not None
    assert message["embeds"] is None


def test_leaderboard_command_has_no_metric_option():
    option_names = [param.name for param in LeaderboardCog.leaderboard.parameters]
    assert option_names == []


@pytest.mark.usefixtures("tmp_db")
async def test_leaderboard_entries_rank_by_hours_played(monkeypatch):
    await db.upsert_pubg_link(1, "account-1", "steam", "PlayerOne")
    await db.upsert_pubg_link(2, "account-2", "steam", "PlayerTwo")
    await db.upsert_match_summary(
        {
            "match_id": "match-1",
            "pubg_account_id": "account-1",
            "platform": "steam",
            "game_mode": "squad-fpp",
            "played_at": "2099-01-10T00:00:00Z",
            "kills": 2,
            "damage": 100.0,
            "assists": 1,
            "revives": 0,
            "survival_time_seconds": 7200,
        }
    )
    await db.upsert_match_summary(
        {
            "match_id": "match-2",
            "pubg_account_id": "account-1",
            "platform": "steam",
            "game_mode": "squad-fpp",
            "played_at": "2099-01-11T00:00:00Z",
            "kills": 1,
            "damage": 50.0,
            "assists": 0,
            "revives": 0,
            "survival_time_seconds": 1800,
        }
    )
    await db.upsert_match_summary(
        {
            "match_id": "match-3",
            "pubg_account_id": "account-2",
            "platform": "steam",
            "game_mode": "squad-fpp",
            "played_at": "2099-01-12T00:00:00Z",
            "kills": 4,
            "damage": 200.0,
            "assists": 2,
            "revives": 0,
            "survival_time_seconds": 5400,
        }
    )
    cog = LeaderboardCog(SimpleNamespace())
    rows = await db.list_pubg_links()

    async def no_refresh(_rows):
        return None

    monkeypatch.setattr(cog, "_refresh_recent_matches", no_refresh)

    entries = await cog._entries(rows)

    assert entries == [
        "`[#1]` **PlayerOne** :: `2.5h | 2 matches`",
        "`[#2]` **PlayerTwo** :: `1.5h | 1 matches`",
    ]
