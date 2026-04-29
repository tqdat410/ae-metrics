from __future__ import annotations

import logging
from datetime import date
import time
from types import SimpleNamespace

import discord
from discord import app_commands
from discord.ext import commands

from bot import cache, db
from bot.embeds import make_compare_embed, make_matches_embed, make_message_embed, make_profile_embed
from bot.providers import get_provider
from bot.rate_limiter import throttle
from bot.validators import PROFILE_VIEWS, PUBG_PLATFORMS, validate_platform, validate_profile_view

LOGGER = logging.getLogger(__name__)
PLATFORM_CHOICES = [app_commands.Choice(name=value, value=value) for value in PUBG_PLATFORMS]
VIEW_CHOICES = [app_commands.Choice(name=value, value=value) for value in PROFILE_VIEWS]


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

    @app_commands.command(name="profile", description="Show a linked PUBG profile")
    @app_commands.choices(view=VIEW_CHOICES)
    async def profile(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        view: str = "ranked",
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        target = user or interaction.user
        try:
            view = validate_profile_view(view)
            link = await db.get_pubg_link(target.id)
            if not link:
                await interaction.followup.send(
                    embed=make_message_embed("No linked account", f"{target.mention} has not linked PUBG yet."),
                    ephemeral=True,
                )
                return
            account = _account_from_link(link)
            payload = await self._profile_payload(account, view)
            await interaction.followup.send(embed=make_profile_embed(account, view, payload), ephemeral=True)
        except Exception as exc:
            LOGGER.exception("Profile lookup failed")
            await interaction.followup.send(
                embed=make_message_embed("Profile lookup failed", _friendly_error(exc), color=0xDC2626),
                ephemeral=True,
            )

    @app_commands.command(name="lookup", description="Look up a PUBG account without linking it")
    @app_commands.choices(platform=PLATFORM_CHOICES, view=VIEW_CHOICES)
    async def lookup(
        self,
        interaction: discord.Interaction,
        name: str,
        platform: str = "steam",
        view: str = "ranked",
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            platform = validate_platform(platform)
            view = validate_profile_view(view)
            account = await self.provider.lookup_account(name.strip(), None, platform)
            payload = await self._profile_payload(account, view)
            await interaction.followup.send(embed=make_profile_embed(account, view, payload), ephemeral=True)
        except Exception as exc:
            LOGGER.exception("Direct lookup failed")
            await interaction.followup.send(
                embed=make_message_embed("Lookup failed", _friendly_error(exc), color=0xDC2626),
                ephemeral=True,
            )

    @app_commands.command(name="compare", description="Compare two linked PUBG members")
    @app_commands.choices(view=VIEW_CHOICES)
    async def compare(
        self,
        interaction: discord.Interaction,
        user_a: discord.Member,
        user_b: discord.Member,
        view: str = "ranked",
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            view = validate_profile_view(view)
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
            left = await self._profile_payload(left_account, view)
            right = await self._profile_payload(right_account, view)
            await interaction.followup.send(
                embed=make_compare_embed(view, user_a.display_name, user_b.display_name, left, right),
                ephemeral=True,
            )
        except Exception as exc:
            LOGGER.exception("Compare failed")
            await interaction.followup.send(
                embed=make_message_embed("Compare failed", _friendly_error(exc), color=0xDC2626),
                ephemeral=True,
            )

    @app_commands.command(name="matches", description="Show recent PUBG matches for a linked member")
    async def matches(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        count: app_commands.Range[int, 1, 5] = 5,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
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
            matches = await self._recent_matches(account, count)
            await interaction.followup.send(
                embed=make_matches_embed(account.canonical_name, matches),
                ephemeral=True,
            )
        except Exception as exc:
            LOGGER.exception("Recent matches failed")
            await interaction.followup.send(
                embed=make_message_embed("Recent matches failed", _friendly_error(exc), color=0xDC2626),
                ephemeral=True,
            )

    async def _profile_payload(self, account: SimpleNamespace, view: str) -> dict:
        fetcher = self.provider.fetch_ranked_view if view == "ranked" else self.provider.fetch_lifetime_view
        await throttle(f"pubg_{view}")
        payload, was_fetched = await cache.get_or_fetch_view(
            account.account_id,
            account.region,
            view,
            lambda: fetcher(account),
        )
        if was_fetched:
            await db.upsert_stat_snapshot(account.account_id, account.region, view, date.today().isoformat(), payload)
        return payload

    async def _recent_matches(self, account: SimpleNamespace, limit: int) -> list[dict]:
        await throttle("pubg_matches")
        recent_ids = await self.provider.fetch_recent_match_ids(account, limit=max(limit, 5))
        cursor = await db.get_match_cursor(account.account_id, account.region) or {}
        seen_ids = set(cursor.get("recent_match_ids") or [])

        for match_id in recent_ids:
            if match_id in seen_ids:
                continue
            summary = await self.provider.fetch_match_summary(account, match_id)
            await db.upsert_match_summary(summary)

        await db.set_match_cursor(
            account.account_id,
            account.region,
            {"recent_match_ids": recent_ids, "fetched_at": int(time.time())},
        )
        stored = await db.list_recent_match_summaries(account.account_id, account.region, limit=limit)
        if stored:
            return stored
        return [await self.provider.fetch_match_summary(account, match_id) for match_id in recent_ids[:limit]]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StatsCog(bot))
