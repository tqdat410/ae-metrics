from __future__ import annotations

import logging
from types import SimpleNamespace

import discord
from discord import app_commands
from discord.ext import commands

from bot import cache, db
from bot.embeds import make_message_embed, tier_weight
from bot.providers import get_provider
from bot.rate_limiter import throttle
from bot.validators import validate_game

GAME_CHOICES = [
    app_commands.Choice(name="League of Legends", value="lol"),
    app_commands.Choice(name="Valorant", value="valo"),
    app_commands.Choice(name="PUBG", value="pubg"),
]
LOGGER = logging.getLogger(__name__)


def _account_from_link(link: dict):
    return SimpleNamespace(
        puuid=link.get("puuid"),
        summoner_id=link.get("summoner_id"),
        account_id=link.get("account_id"),
        canonical_name=link.get("game_name"),
        tag_line=link.get("tag_line"),
        region=link.get("region"),
    )


def _read(obj, name: str, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Show linked members ranked for a game")
    @app_commands.choices(game=GAME_CHOICES)
    async def leaderboard(self, interaction: discord.Interaction, game: str) -> None:
        await interaction.response.defer()
        try:
            game = validate_game(game)
            rows = await db.list_links_by_game(game)
            if not rows:
                await interaction.followup.send(embed=make_message_embed("Leaderboard", f"No `{game}` links yet."))
                return
            entries = await self._entries(game, rows[:10])
            embed = discord.Embed(title=f"{game.upper()} leaderboard", color=0x2563EB)
            embed.description = "\n".join(entries) if entries else "No ranks available right now."
            await interaction.followup.send(embed=embed)
        except Exception:
            LOGGER.exception("Leaderboard failed for game %s", game)
            await interaction.followup.send(
                embed=make_message_embed("Leaderboard failed", "Could not build leaderboard right now.", color=0xDC2626)
            )

    async def _entries(self, game: str, rows: list[dict]) -> list[str]:
        provider = get_provider(game)
        ranked = []
        for row in rows:
            account = _account_from_link(row)
            try:
                await throttle(game)
                rank = await cache.get_or_fetch_rank(row["discord_id"], game, account, provider)
                ranked.append((tier_weight(_read(rank, "tier"), _read(rank, "division"), _read(rank, "points")), row, rank))
            except Exception:
                LOGGER.exception("Skipping leaderboard row for discord_id=%s game=%s", row.get("discord_id"), game)
                continue
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [self._line(index, row, rank) for index, (_, row, rank) in enumerate(ranked, start=1)]

    def _line(self, index: int, row: dict, rank) -> str:
        tag = f"#{row['tag_line']}" if row.get("tag_line") else ""
        tier = _read(rank, "tier") or "Unranked"
        division = _read(rank, "division")
        points = _read(rank, "points")
        score = f"{tier}{f' {division}' if division else ''}"
        if points is not None:
            score += f" - {points} pts"
        return f"**{index}.** <@{row['discord_id']}> - `{row['game_name']}{tag}` - {score}"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
