from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import db
from bot.embeds import make_message_embed
from bot.providers import get_provider
from bot.validators import parse_riot_id, validate_game, validate_region

GAME_CHOICES = [
    app_commands.Choice(name="League of Legends", value="lol"),
    app_commands.Choice(name="Valorant", value="valo"),
    app_commands.Choice(name="PUBG", value="pubg"),
]
LOGGER = logging.getLogger(__name__)

LOL_REGIONS = [app_commands.Choice(name=value, value=value) for value in ("vn2", "na1", "euw1", "kr")]
VALO_REGIONS = [app_commands.Choice(name=value, value=value) for value in ("ap", "eu", "na", "kr")]
PUBG_PLATFORMS = [app_commands.Choice(name=value, value=value) for value in ("steam", "kakao", "xbox", "psn")]


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
    return "Game API is unavailable right now. Try again later."


def _read(obj, name: str, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


class LinkCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    link = app_commands.Group(name="link", description="Link a game account")

    @link.command(name="lol", description="Link a League of Legends Riot ID")
    @app_commands.choices(region=LOL_REGIONS)
    async def link_lol(self, interaction: discord.Interaction, riot_id: str, region: str = "vn2") -> None:
        await interaction.response.defer(ephemeral=True)
        await self._link_riot_game(interaction, "lol", riot_id, region)

    @link.command(name="valo", description="Link a Valorant Riot ID")
    @app_commands.choices(region=VALO_REGIONS)
    async def link_valo(self, interaction: discord.Interaction, riot_id: str, region: str = "ap") -> None:
        await interaction.response.defer(ephemeral=True)
        await self._link_riot_game(interaction, "valo", riot_id, region)

    @link.command(name="pubg", description="Link a PUBG account")
    @app_commands.choices(platform=PUBG_PLATFORMS)
    async def link_pubg(self, interaction: discord.Interaction, name: str, platform: str = "steam") -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            platform = validate_region("pubg", platform)
            account = await get_provider("pubg").lookup_account(name.strip(), None, platform)
            await self._save_link(interaction.user.id, "pubg", account)
            embed = make_message_embed("PUBG linked", f"Linked `{_read(account, 'canonical_name', name)}` on `{platform}`.")
        except Exception as exc:
            LOGGER.exception("Failed to link PUBG account")
            embed = make_message_embed("Link failed", _friendly_error(exc), color=0xDC2626)
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _link_riot_game(self, interaction: discord.Interaction, game: str, riot_id: str, region: str) -> None:
        try:
            name, tag = parse_riot_id(riot_id)
            region = validate_region(game, region)
            account = await get_provider(game).lookup_account(name, tag, region)
            await self._save_link(interaction.user.id, game, account)
            embed = make_message_embed(f"{game.upper()} linked", f"Linked `{name}#{tag}` on `{region}`.")
        except Exception as exc:
            LOGGER.exception("Failed to link Riot account for %s", game)
            embed = make_message_embed("Link failed", _friendly_error(exc), color=0xDC2626)
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _save_link(self, discord_id: int, game: str, account) -> None:
        await db.upsert_link(
            discord_id=discord_id,
            game=game,
            region=_read(account, "region"),
            game_name=_read(account, "canonical_name"),
            tag_line=_read(account, "tag_line"),
            puuid=_read(account, "puuid"),
            summoner_id=_read(account, "summoner_id"),
            account_id=_read(account, "account_id"),
        )

    @app_commands.command(name="unlink", description="Unlink one game account")
    @app_commands.choices(game=GAME_CHOICES)
    async def unlink(self, interaction: discord.Interaction, game: str) -> None:
        await interaction.response.defer(ephemeral=True)
        game = validate_game(game)
        deleted = await db.delete_link(interaction.user.id, game)
        message = f"Unlinked your `{game}` account." if deleted else f"No `{game}` account was linked."
        await interaction.followup.send(embed=make_message_embed("Unlink complete", message), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LinkCog(bot))
