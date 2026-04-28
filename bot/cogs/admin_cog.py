from __future__ import annotations

import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import dotenv_values

from bot.config import get_settings
from bot.embeds import make_message_embed
from bot.key_monitor import mark_riot_key_reloaded


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    admin = app_commands.Group(name="admin", description="Bot admin commands")

    @admin.command(name="reload-key", description="Reload the Riot development key from .env")
    async def reload_key(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        admin_id = getattr(self.bot.settings, "admin_discord_id", None)
        if not admin_id or interaction.user.id != admin_id:
            await interaction.followup.send(
                embed=make_message_embed("Not allowed", "Only the configured bot admin can reload keys.", color=0xDC2626),
                ephemeral=True,
            )
            return

        env_values = dotenv_values(Path(".env"))
        key = str(env_values.get("RIOT_API_KEY") or "").strip()
        if not key:
            await interaction.followup.send(
                embed=make_message_embed("Invalid key", "Update RIOT_API_KEY in `.env`, then run this command.", color=0xDC2626),
                ephemeral=True,
            )
            return

        os.environ["RIOT_API_KEY"] = key
        get_settings.cache_clear()
        self.bot.settings.riot_api_key = key
        await mark_riot_key_reloaded()
        await interaction.followup.send(
            embed=make_message_embed("Riot key reloaded", "RIOT_API_KEY from `.env` is active for future requests."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
