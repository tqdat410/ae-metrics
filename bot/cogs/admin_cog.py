from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import db
from bot.embeds import make_message_embed
from bot.permissions import is_admin
from bot.providers import get_provider
from bot.validators import PUBG_PLATFORMS, validate_platform

LOGGER = logging.getLogger(__name__)
PLATFORM_CHOICES = [app_commands.Choice(name=value, value=value) for value in PUBG_PLATFORMS]


def _not_allowed() -> discord.Embed:
    return make_message_embed("Not allowed", "Only bot admins can manage another member's link.", color=0xDC2626)


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
    return "Could not update the member PUBG link right now."


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    admin = app_commands.Group(name="admin", description="Bot admin commands")
    link = app_commands.Group(name="link", description="Manage member PUBG links", parent=admin)

    @link.command(name="set", description="Set or replace another member's PUBG link")
    @app_commands.choices(platform=PLATFORM_CHOICES)
    async def link_set(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        name: str,
        platform: str = "steam",
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not is_admin(interaction):
            await interaction.followup.send(embed=_not_allowed(), ephemeral=True)
            return

        try:
            platform = validate_platform(platform)
            provider = get_provider()
            account = await provider.lookup_account(name.strip(), None, platform)
            await db.upsert_pubg_link(
                user.id,
                account.account_id,
                account.region,
                account.canonical_name,
                linked_by_admin_id=interaction.user.id,
            )
            message = f"Linked {user.mention} to `{account.canonical_name}` on `{platform}`."
            embed = make_message_embed("Admin link updated", message)
        except Exception as exc:
            LOGGER.exception("Admin link set failed")
            embed = make_message_embed("Admin link failed", _friendly_error(exc), color=0xDC2626)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @link.command(name="delete", description="Delete another member's PUBG link")
    async def link_delete(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await interaction.response.defer(ephemeral=True)
        if not is_admin(interaction):
            await interaction.followup.send(embed=_not_allowed(), ephemeral=True)
            return

        deleted = await db.delete_pubg_link(user.id)
        message = f"Removed PUBG link for {user.mention}." if deleted else f"{user.mention} has no PUBG link."
        await interaction.followup.send(embed=make_message_embed("Admin link delete", message), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
