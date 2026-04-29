from types import SimpleNamespace

import discord
import pytest

from bot.compare_view import CompareView, build_compare_embed


def _payload(rank_points: int, *, tier: str = "GOLD", division: str = "2", wins: int = 10, matches: int = 40, kd: float = 2.0, avg_damage: float = 250.0) -> dict:
    return {
        "generated_at": "2026-04-29T00:00:00+00:00",
        "ranked": {"tier": tier, "division": division, "points": rank_points, "wins": wins, "matches": matches, "kd": kd, "mode": "squad-fpp"},
        "lifetime": {"wins": wins * 2, "matches": matches * 5, "top10s": 90, "kd": kd - 0.2, "kills": 250, "damage": 40000.0, "headshots": 20, "assists": 30, "revives": 10, "longest_kill": 200.0, "avg_survival_time": 900.0},
        "recent": {"sample_size": 20, "wins": 2, "avg_placement": 4.5, "avg_kills": 3.0, "avg_damage": avg_damage, "top10_rate": 50.0, "avg_survival_time_seconds": 1000.0, "matches": []},
    }


def test_build_compare_embed_all_only_shows_lifetime_metrics():
    embed = build_compare_embed("all", "Alpha", "Bravo", _payload(1500, tier="GOLD", division="2"), _payload(900, tier="SILVER", division="1"))

    assert embed.title == "So sánh: Alpha vs Bravo"
    assert embed.description == "**All**  |  Lifetime core stats"
    assert all(field.name != "Lifetime" for field in embed.fields)
    assert all(field.name != "Tier" for field in embed.fields)
    top10_field = next(field for field in embed.fields if field.name == "Top 10 Rate")
    assert "█" in top10_field.value


def test_build_compare_embed_rank_uses_short_tier_and_bars():
    embed = build_compare_embed("rank", "Alpha", "Bravo", _payload(1500, tier="GOLD", division="2"), _payload(900, tier="SILVER", division="1"))

    assert all(field.name != "Rank" for field in embed.fields)
    tier_field = next(field for field in embed.fields if field.name == "Tier")
    assert "G2" in tier_field.value
    assert "S1" in tier_field.value
    assert "██████████" in tier_field.value


def test_build_compare_embed_recent_shows_avg_20_games():
    embed = build_compare_embed("recent", "Alpha", "Bravo", _payload(1500, avg_damage=300), _payload(1200, avg_damage=150))

    assert embed.description == "**Recent**  |  Avg. 20 Games"
    avg_damage_field = next(field for field in embed.fields if field.name == "Avg Damage")
    assert "300" in avg_damage_field.value
    assert "150" in avg_damage_field.value
    assert "█" in avg_damage_field.value


@pytest.mark.asyncio
async def test_compare_view_switches_pages_and_disables_on_timeout():
    view = CompareView("Alpha", "Bravo", _payload(1500), _payload(1200))
    message_edits = []

    async def edit(**kwargs):
        message_edits.append(kwargs)

    class FakeResponse:
        async def edit_message(self, **kwargs):
            message_edits.append(kwargs)

    interaction = SimpleNamespace(response=FakeResponse())
    view.message = SimpleNamespace(edit=edit)

    assert view.page == "all"
    assert any(isinstance(child, discord.ui.Button) and child.style == discord.ButtonStyle.primary and child.label == "All" for child in view.children)

    await view._swap_page(interaction, "recent")

    assert view.page == "recent"
    assert isinstance(message_edits[0]["embed"], discord.Embed)
    assert any(isinstance(child, discord.ui.Button) and child.style == discord.ButtonStyle.primary and child.label == "Recent" for child in view.children)

    await view._swap_page(interaction, "rank")

    assert view.page == "rank"
    assert any(isinstance(child, discord.ui.Button) and child.style == discord.ButtonStyle.primary and child.label == "Rank" for child in view.children)

    await view.on_timeout()

    assert all(not isinstance(child, discord.ui.Button) or child.disabled for child in view.children)
    assert message_edits[-1]["view"] is view
