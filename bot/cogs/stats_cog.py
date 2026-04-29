from __future__ import annotations

import logging
from types import SimpleNamespace

import discord
from discord import app_commands
from discord.ext import commands

from bot import db
from bot.compare_view import CompareView
from bot.embeds import make_message_embed
from bot.profile_view import ProfileView
from bot.profile_hub_service import ProfileHubService
from bot.providers import get_provider
from bot.validators import (
    PROFILE_VISIBILITIES,
    PUBG_PLATFORMS,
    validate_platform,
    validate_profile_visibility,
)

LOGGER = logging.getLogger(__name__)
PLATFORM_CHOICES = [app_commands.Choice(name=value, value=value) for value in PUBG_PLATFORMS]
VISIBILITY_CHOICES = [app_commands.Choice(name=value, value=value) for value in PROFILE_VISIBILITIES]


def _friendly_error(exc: Exception) -> str:
    name = exc.__class__.__name__
    if name == "NotFoundError":
        return "PUBG account or stats not found."
    if name == "RateLimitError":
        return "PUBG API rate limit hit. Try again in a minute."
    if name == "ApiKeyError":
        return "PUBG API key is invalid or expired."
    if isinstance(exc, ValueError):
        return str(exc)
    return "Could not fetch PUBG stats right now. Try again later."


def _account_from_link(link: dict) -> SimpleNamespace:
    return SimpleNamespace(
        account_id=link["pubg_account_id"],
        canonical_name=link["canonical_name"],
        region=link["platform"],
    )


class StatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.provider = get_provider()
        self.profile_hub = ProfileHubService(self.provider)

    @app_commands.command(name="profile", description="Show a linked PUBG overview")
    @app_commands.choices(visibility=VISIBILITY_CHOICES)
    async def profile(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        visibility: str = "private",
    ) -> None:
        visibility = validate_profile_visibility(visibility)
        await interaction.response.defer(ephemeral=visibility == "private")
        target = user or interaction.user
        try:
            link = await db.get_pubg_link(target.id)
            if not link:
                await interaction.followup.send(
                    embed=make_message_embed("No linked account", f"{target.mention} has not linked PUBG yet."),
                    ephemeral=True,
                )
                return
            account = _account_from_link(link)
            await self._send_profile_response(interaction, account, visibility=visibility)
        except Exception as exc:
            LOGGER.exception("Profile lookup failed")
            await interaction.followup.send(
                embed=make_message_embed("Profile lookup failed", _friendly_error(exc), color=0xDC2626),
                ephemeral=True,
            )

    @app_commands.command(name="lookup", description="Look up a PUBG account overview without linking it")
    @app_commands.choices(platform=PLATFORM_CHOICES)
    async def lookup(
        self,
        interaction: discord.Interaction,
        name: str,
        platform: str = "steam",
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            platform = validate_platform(platform)
            account = await self.provider.lookup_account(name.strip(), None, platform)
            await self._send_profile_response(interaction, account, visibility="private")
        except Exception as exc:
            LOGGER.exception("Direct lookup failed")
            await interaction.followup.send(
                embed=make_message_embed("Lookup failed", _friendly_error(exc), color=0xDC2626),
                ephemeral=True,
            )

    @app_commands.command(name="compare", description="Compare two linked PUBG members")
    async def compare(
        self,
        interaction: discord.Interaction,
        user_a: discord.Member,
        user_b: discord.Member,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            left_link = await db.get_pubg_link(user_a.id)
            right_link = await db.get_pubg_link(user_b.id)
            if not left_link or not right_link:
                await interaction.followup.send(
                    embed=make_message_embed("Compare unavailable", "Both members must link PUBG first."),
                    ephemeral=True,
                )
                return

            left_account = _account_from_link(left_link)
            right_account = _account_from_link(right_link)
            left = await self.profile_hub.build(left_account)
            right = await self.profile_hub.build(right_account)
            view = CompareView(user_a.display_name, user_b.display_name, left, right)
            message = await interaction.followup.send(
                embed=view.current_embed(),
                view=view,
                ephemeral=True,
                wait=True,
            )
            view.message = message
        except Exception as exc:
            LOGGER.exception("Compare failed")
            await interaction.followup.send(
                embed=make_message_embed("Compare failed", _friendly_error(exc), color=0xDC2626),
                ephemeral=True,
            )

    async def _send_profile_response(
        self,
        interaction: discord.Interaction,
        account: SimpleNamespace,
        *,
        visibility: str,
    ) -> None:
        payload = await self.profile_hub.build(account)
        view = ProfileView(account, payload)
        message = await interaction.followup.send(
            embed=view.current_embed(),
            view=view,
            ephemeral=visibility == "private",
            wait=True,
        )
        view.message = message


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StatsCog(bot))
