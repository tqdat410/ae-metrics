from __future__ import annotations

import logging
from types import SimpleNamespace

import discord
from discord import app_commands
from discord.ext import commands

from bot import cache, db
from bot.embeds import make_leaderboard_embed, make_message_embed, tier_weight
from bot.providers import get_provider
from bot.rate_limiter import throttle
from bot.validators import LEADERBOARD_METRICS, validate_leaderboard_metric

LOGGER = logging.getLogger(__name__)
METRIC_CHOICES = [app_commands.Choice(name=value, value=value) for value in LEADERBOARD_METRICS]


def _account_from_link(link: dict) -> SimpleNamespace:
    return SimpleNamespace(
        account_id=link["pubg_account_id"],
        canonical_name=link["canonical_name"],
        region=link["platform"],
    )


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.provider = get_provider()

    @app_commands.command(name="leaderboard", description="Show the PUBG leaderboard for linked members")
    @app_commands.choices(metric=METRIC_CHOICES)
    async def leaderboard(self, interaction: discord.Interaction, metric: str = "rank_points") -> None:
        await interaction.response.defer()
        try:
            metric = validate_leaderboard_metric(metric)
            rows = await db.list_pubg_links()
            if not rows:
                await interaction.followup.send(embed=make_message_embed("Leaderboard", "No PUBG links yet."))
                return
            entries = await self._entries(metric, rows[:10])
            await interaction.followup.send(embed=make_leaderboard_embed(metric, entries))
        except Exception:
            LOGGER.exception("Leaderboard failed")
            await interaction.followup.send(
                embed=make_message_embed("Leaderboard failed", "Could not build the PUBG leaderboard right now.", color=0xDC2626)
            )

    async def _entries(self, metric: str, rows: list[dict]) -> list[str]:
        ranked = []
        for row in rows:
            account = _account_from_link(row)
            try:
                payload = await self._metric_payload(account, metric)
                ranked.append((self._metric_score(metric, payload), row, payload))
            except Exception:
                LOGGER.exception("Skipping leaderboard row for discord_user_id=%s", row.get("discord_user_id"))
                continue
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [self._line(index, row, metric, payload) for index, (_, row, payload) in enumerate(ranked, start=1)]

    async def _metric_payload(self, account: SimpleNamespace, metric: str) -> dict:
        view = "lifetime" if metric in {"kd", "damage"} else "ranked"
        fetcher = self.provider.fetch_lifetime_view if view == "lifetime" else self.provider.fetch_ranked_view
        await throttle(f"pubg_{metric}")
        payload, _ = await cache.get_or_fetch_view(account.account_id, account.region, view, lambda: fetcher(account))
        return payload

    def _metric_score(self, metric: str, payload: dict) -> float:
        if metric == "rank_points":
            return float(tier_weight(payload.get("tier"), payload.get("division"), payload.get("points")))
        if metric == "wins":
            return float(payload.get("wins") or 0)
        if metric == "kd":
            return float(payload.get("kd") or 0)
        if metric == "damage":
            return float(payload.get("damage") or 0)
        return 0.0

    def _line(self, index: int, row: dict, metric: str, payload: dict) -> str:
        if metric == "rank_points":
            tier = payload.get("tier") or "Unranked"
            division = payload.get("division")
            value = f"{tier}{f' {division}' if division else ''}"
            if payload.get("points") is not None:
                value += f" - {payload['points']} pts"
        elif metric == "wins":
            value = f"{payload.get('wins') or 0} wins"
        elif metric == "kd":
            value = f"{float(payload.get('kd') or 0):.2f} K/D"
        else:
            value = f"{int(payload.get('damage') or 0)} damage"
        return f"**{index}.** <@{row['discord_user_id']}> - `{row['canonical_name']}` - {value}"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
