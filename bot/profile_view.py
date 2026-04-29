from __future__ import annotations

from typing import Any, Literal

import discord

from bot.profile_embeds import build_profile_embed

ProfilePage = Literal["all", "recent", "rank"]


class ProfileView(discord.ui.View):
    def __init__(self, account: Any, payload: dict[str, Any]) -> None:
        super().__init__(timeout=600)
        self.account = account
        self.payload = payload
        self.page: ProfilePage = "all"
        self.message: Any | None = None
        self._sync_buttons()

    def current_embed(self) -> discord.Embed:
        return build_profile_embed(self.page, self.account, self.payload)

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message is not None and hasattr(self.message, "edit"):
            await self.message.edit(view=self)

    @discord.ui.button(label="All", style=discord.ButtonStyle.primary)
    async def all_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._swap_page(interaction, "all")

    @discord.ui.button(label="Recent", style=discord.ButtonStyle.secondary)
    async def recent_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._swap_page(interaction, "recent")

    @discord.ui.button(label="Rank", style=discord.ButtonStyle.secondary)
    async def rank_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._swap_page(interaction, "rank")

    async def _swap_page(self, interaction: discord.Interaction, page: ProfilePage) -> None:
        self.page = page
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    def _sync_buttons(self) -> None:
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            active = (child.label == "All" and self.page == "all") or (child.label == "Recent" and self.page == "recent") or (child.label == "Rank" and self.page == "rank")
            child.style = discord.ButtonStyle.primary if active else discord.ButtonStyle.secondary
