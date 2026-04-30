from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot import db
from bot.embeds import make_leaderboard_embeds, make_message_embed
from bot.validators import PROFILE_VISIBILITIES, validate_profile_visibility

VISIBILITY_CHOICES = [app_commands.Choice(name=value, value=value) for value in PROFILE_VISIBILITIES]

LOGGER = logging.getLogger(__name__)
ACTIVITY_WINDOW_DAYS = 7
TOP_ROWS = 10


def _activity_cutoff_unix(days: int = ACTIVITY_WINDOW_DAYS) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Show the PUBG activity leaderboard for linked members")
    @app_commands.choices(visibility=VISIBILITY_CHOICES)
    async def leaderboard(self, interaction: discord.Interaction, visibility: str = "public") -> None:
        visibility = validate_profile_visibility(visibility)
        ephemeral = visibility == "private"
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            rows = await db.list_pubg_links()
            if not rows:
                await interaction.followup.send(embed=make_message_embed("Leaderboard", "No PUBG links yet."), ephemeral=ephemeral)
                return
            entries = await self._entries(rows, guild=interaction.guild)
            await interaction.followup.send(embeds=make_leaderboard_embeds(entries), ephemeral=ephemeral)
        except Exception:
            LOGGER.exception("Leaderboard failed")
            await interaction.followup.send(
                embed=make_message_embed("Leaderboard failed", "Could not build the PUBG leaderboard right now.", color=0xDC2626),
                ephemeral=ephemeral,
            )

    async def _entries(self, rows: list[dict], *, guild: discord.Guild | None = None) -> list[str]:
        nghien_custom = _custom_emoji(guild, "4210_7") or ""
        co_lap_custom = _custom_emoji(guild, "zhuy_st50k") or ""
        top2_custom = _custom_emoji(guild, "le_5") or "🔥"
        top3_custom = _custom_emoji(guild, "lgbt8") or "🔥"
        activity_rows = await db.list_match_activity_since_unix(_activity_cutoff_unix())
        activity_by_account = {(item["pubg_account_id"], item["platform"]): item for item in activity_rows}

        synced: list[tuple[float, dict, dict]] = []
        syncing: list[tuple[float, dict, dict]] = []
        inactive: list[tuple[float, dict, dict]] = []
        cutoff_unix = _activity_cutoff_unix()
        for row in rows:
            activity = activity_by_account.get((row["pubg_account_id"], row["platform"])) or {
                "match_count": 0,
                "total_survival_seconds": 0,
            }
            score = float(activity.get("total_survival_seconds") or 0)
            cursor = await db.get_match_cursor(row["pubg_account_id"], row["platform"]) or {}
            is_synced = bool(cursor.get("full_7d_sync")) or (
                cursor.get("covered_until_unix") is not None and int(cursor["covered_until_unix"]) <= cutoff_unix
            )
            if int(activity.get("match_count") or 0) <= 0:
                bucket = inactive
            else:
                bucket = synced if is_synced else syncing
            bucket.append((score, row, activity))

        synced.sort(key=lambda item: item[0], reverse=True)
        syncing.sort(key=lambda item: item[0], reverse=True)
        ranked = synced[:TOP_ROWS] if len(synced) > TOP_ROWS else synced + syncing + inactive
        return [
            self._line(
                index,
                row,
                activity,
                syncing=index > len(synced) and int(activity.get("match_count") or 0) > 0,
                nghien_custom=nghien_custom,
                co_lap_custom=co_lap_custom,
                top2_emoji=top2_custom,
                top3_emoji=top3_custom,
            )
            for index, (_, row, activity) in enumerate(ranked, start=1)
        ]

    def _line(
        self,
        index: int,
        row: dict,
        activity: dict,
        *,
        syncing: bool = False,
        nghien_custom: str = "",
        co_lap_custom: str = "",
        top2_emoji: str = "🔥",
        top3_emoji: str = "🔥",
    ) -> str:
        matches = int(activity.get("match_count") or 0)
        hours = float(activity.get("total_survival_seconds") or 0) / 3600
        rank = _rank_badge(index)
        suffix = " · _đang đồng bộ_" if syncing else ""
        if matches <= 0:
            trail = f" {co_lap_custom}" if co_lap_custom else ""
            return f"{rank} **{row['canonical_name']}** — 💀 _Bị Huy cô lập_{trail}{suffix}"
        if index == 1:
            trail = f" {nghien_custom}" if nghien_custom else ""
            label = f" · 🚨 _Nghiện nặng_{trail}"
        elif index == 2:
            label = f" · {top2_emoji}"
        elif index == 3:
            label = f" · {top3_emoji}"
        else:
            label = ""
        per_day = hours / ACTIVITY_WINDOW_DAYS
        return (
            f"{rank} **{row['canonical_name']}** — "
            f"`{hours:.1f}h` · {matches} trận · {per_day:.1f}h/ngày{label}{suffix}"
        )


_RANK_BADGES = {1: "🥇", 2: "🥈", 3: "🥉"}


def _rank_badge(index: int) -> str:
    return _RANK_BADGES.get(index, f"`#{index:>2}`")


def _custom_emoji(guild: discord.Guild | None, name: str) -> str | None:
    """Resolve a server custom emoji by name to its <:name:id> render token.

    Returns None if the guild is missing or the emoji isn't found, so callers
    can fall back to a unicode default.
    """
    if guild is None:
        return None
    for emoji in guild.emojis:
        if emoji.name == name:
            prefix = "a" if emoji.animated else ""
            return f"<{prefix}:{emoji.name}:{emoji.id}>"
    return None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
