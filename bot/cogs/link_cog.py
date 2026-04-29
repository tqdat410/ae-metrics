from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import db
from bot.embeds import make_message_embed
from bot.providers import get_provider
from bot.validators import PUBG_PLATFORMS, validate_platform

LOGGER = logging.getLogger(__name__)
PLATFORM_CHOICES = [app_commands.Choice(name=value, value=value) for value in PUBG_PLATFORMS]


def _friendly_error(exc: Exception) -> str:
    name = exc.__class__.__name__
    if name == "NotFoundError":
        return "PUBG account not found. Double-check the name and platform."
    if name == "RateLimitError":
        return "PUBG API rate limit hit. Try again in a minute."
    if name == "ApiKeyError":
        return "PUBG API key is invalid or expired."
    if isinstance(exc, ValueError):
        return str(exc)
    return "PUBG API is unavailable right now. Try again later."


class LinkCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    link = app_commands.Group(name="link", description="Link a PUBG account")

    @link.command(name="pubg", description="Link your PUBG account")
    @app_commands.choices(platform=PLATFORM_CHOICES)
    async def link_pubg(self, interaction: discord.Interaction, name: str, platform: str = "steam") -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            platform = validate_platform(platform)
            provider = get_provider()
            account = await provider.lookup_account(name.strip(), None, platform)
            await db.upsert_pubg_link(
                interaction.user.id,
                account.account_id,
                account.region,
                account.canonical_name,
            )
            embed = make_message_embed("PUBG linked", f"Linked `{account.canonical_name}` on `{platform}`.")
        except Exception as exc:
            LOGGER.exception("Failed to link PUBG account")
            embed = make_message_embed("Link failed", _friendly_error(exc), color=0xDC2626)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="unlink", description="Unlink your PUBG account")
    async def unlink(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        deleted = await db.delete_pubg_link(interaction.user.id)
        message = "Unlinked your PUBG account." if deleted else "No PUBG account was linked."
        await interaction.followup.send(embed=make_message_embed("Unlink complete", message), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LinkCog(bot))
