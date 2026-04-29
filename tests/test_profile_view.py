from types import SimpleNamespace

import discord
import pytest

from bot.profile_embeds import build_profile_embed
from bot.profile_view import ProfileView


def _payload() -> dict:
    return {
        "generated_at": "2026-04-29T00:00:00+00:00",
        "metadata": {"name": "PlayerOne", "platform": "steam", "clan_id": "ClanTag"},
        "ranked": {"tier": "GOLD", "division": "2", "points": 1500, "wins": 10, "matches": 40, "kd": 2.0, "mode": "squad-fpp"},
        "lifetime": {"wins": 20, "matches": 200, "top10s": 90, "kd": 1.8, "kills": 250, "damage": 40000.0, "headshots": 20, "assists": 30, "revives": 10, "longest_kill": 200.0, "avg_survival_time": 900.0},
        "recent": {"sample_size": 20, "wins": 2, "avg_placement": 4.5, "avg_kills": 3.0, "avg_damage": 250.0, "top10_rate": 50.0, "avg_survival_time_seconds": 1000.0, "matches": []},
        "mastery": {"survival": {"level": 18}},
    }


def _account() -> SimpleNamespace:
    return SimpleNamespace(canonical_name="PlayerOne")


def test_build_profile_embed_uses_all_recent_rank_tabs():
    all_embed = build_profile_embed("all", _account(), _payload())
    rank_embed = build_profile_embed("rank", _account(), _payload())
    recent_embed = build_profile_embed("recent", _account(), _payload())

    assert all_embed.title == "Game Thủ: PlayerOne"
    assert all(field.name != "Tier" for field in all_embed.fields)
    assert any(field.name == "Tier" for field in rank_embed.fields)
    assert recent_embed.description == "**Recent**  |  Avg. 20 Games"


@pytest.mark.asyncio
async def test_profile_view_switches_pages_and_disables_on_timeout():
    view = ProfileView(_account(), _payload())
    message_edits = []

    async def edit(**kwargs):
        message_edits.append(kwargs)

    class FakeResponse:
        async def edit_message(self, **kwargs):
            message_edits.append(kwargs)

    interaction = SimpleNamespace(response=FakeResponse())
    view.message = SimpleNamespace(edit=edit)

    assert view.page == "all"
    await view._swap_page(interaction, "recent")
    assert isinstance(message_edits[0]["embed"], discord.Embed)
    assert any(isinstance(child, discord.ui.Button) and child.style == discord.ButtonStyle.primary and child.label == "Recent" for child in view.children)

    await view._swap_page(interaction, "rank")
    assert view.page == "rank"
    assert any(isinstance(child, discord.ui.Button) and child.style == discord.ButtonStyle.primary and child.label == "Rank" for child in view.children)

    await view.on_timeout()
    assert all(not isinstance(child, discord.ui.Button) or child.disabled for child in view.children)
    assert message_edits[-1]["view"] is view
