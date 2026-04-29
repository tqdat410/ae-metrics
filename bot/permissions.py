from __future__ import annotations

import discord


def is_admin(interaction: discord.Interaction) -> bool:
    settings = getattr(getattr(interaction, "client", None), "settings", None)
    admin_id = getattr(settings, "admin_discord_id", None)
    if admin_id and interaction.user.id == admin_id:
        return True

    permissions = getattr(interaction.user, "guild_permissions", None)
    return bool(permissions and permissions.administrator)
