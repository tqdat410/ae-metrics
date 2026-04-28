from __future__ import annotations

import logging
from types import SimpleNamespace

import discord
from discord import app_commands
from discord.ext import commands

from bot import cache, db
from bot.embeds import make_message_embed, make_rank_embed
from bot.providers import get_provider
from bot.validators import parse_riot_id, validate_game, validate_region

GAME_CHOICES = [
    app_commands.Choice(name="League of Legends", value="lol"),
    app_commands.Choice(name="Valorant", value="valo"),
    app_commands.Choice(name="PUBG", value="pubg"),
]
LOGGER = logging.getLogger(__name__)


def _friendly_error(exc: Exception) -> str:
    name = exc.__class__.__name__
    if name == "NotFoundError":
        return "Account not found. Double-check the name, tag, and region."
    if name == "RateLimitError":
        return "Game API rate limit hit. Try again in a minute."
    if name == "ApiKeyError":
        return "Game API key is invalid or expired. Ask an admin to reload it."
    if isinstance(exc, ValueError):
        return str(exc)
    return "Could not fetch stats right now. Try again later."


def _account_from_link(link: dict):
    return SimpleNamespace(
        puuid=link.get("puuid"),
        summoner_id=link.get("summoner_id"),
        account_id=link.get("account_id"),
        canonical_name=link.get("game_name"),
        tag_line=link.get("tag_line"),
        region=link.get("region"),
    )


class StatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="rank", description="Show a linked member's rank")
    @app_commands.choices(game=GAME_CHOICES)
    async def rank(
        self,
        interaction: discord.Interaction,
        game: str,
        user: discord.Member | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        target = user or interaction.user
        try:
            game = validate_game(game)
            link = await db.get_link(target.id, game)
            if not link:
                msg = f"{target.mention} has not linked `{game}` yet. Use `/link` first."
                await interaction.followup.send(embed=make_message_embed("No linked account", msg), ephemeral=True)
                return
            account = _account_from_link(link)
            rank_info = await cache.get_or_fetch_rank(target.id, game, account, get_provider(game))
            await interaction.followup.send(embed=make_rank_embed(game, account, rank_info), ephemeral=True)
        except Exception as exc:
            LOGGER.exception("Rank lookup failed for game %s", game)
            await interaction.followup.send(
                embed=make_message_embed("Rank lookup failed", _friendly_error(exc), color=0xDC2626),
                ephemeral=True,
            )

    @app_commands.command(name="lookup", description="Look up an account without linking it")
    @app_commands.choices(game=GAME_CHOICES)
    async def lookup(
        self,
        interaction: discord.Interaction,
        game: str,
        player: str,
        region: str | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            game = validate_game(game)
            provider = get_provider(game)
            if game == "pubg":
                region = validate_region(game, region or "steam")
                account = await provider.lookup_account(player.strip(), None, region)
            else:
                name, tag = parse_riot_id(player)
                region = validate_region(game, region)
                account = await provider.lookup_account(name, tag, region)
            rank_info = await provider.fetch_rank(account)
            await interaction.followup.send(embed=make_rank_embed(game, account, rank_info), ephemeral=True)
        except Exception as exc:
            LOGGER.exception("Direct lookup failed for game %s", game)
            await interaction.followup.send(
                embed=make_message_embed("Lookup failed", _friendly_error(exc), color=0xDC2626),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StatsCog(bot))
