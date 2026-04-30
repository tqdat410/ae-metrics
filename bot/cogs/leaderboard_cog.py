from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot import db
from bot.embeds import make_leaderboard_embed, make_message_embed
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
    async def leaderboard(self, interaction: discord.Interaction, visibility: str = "private") -> None:
        visibility = validate_profile_visibility(visibility)
        ephemeral = visibility == "private"
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            rows = await db.list_pubg_links()
            if not rows:
                await interaction.followup.send(embed=make_message_embed("Leaderboard", "No PUBG links yet."), ephemeral=ephemeral)
                return
            entries = await self._entries(rows)
            await interaction.followup.send(embed=make_leaderboard_embed(entries), ephemeral=ephemeral)
        except Exception:
            LOGGER.exception("Leaderboard failed")
            await interaction.followup.send(
                embed=make_message_embed("Leaderboard failed", "Could not build the PUBG leaderboard right now.", color=0xDC2626),
                ephemeral=ephemeral,
            )

    async def _entries(self, rows: list[dict]) -> list[str]:
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
            self._line(index, row, activity, syncing=index > len(synced) and int(activity.get("match_count") or 0) > 0)
            for index, (_, row, activity) in enumerate(ranked, start=1)
        ]

    def _line(self, index: int, row: dict, activity: dict, *, syncing: bool = False) -> str:
        matches = int(activity.get("match_count") or 0)
        hours = float(activity.get("total_survival_seconds") or 0) / 3600
        rank = _rank_badge(index)
        tier_emoji, tier_label = _addiction_tier(hours, matches)
        per_day = hours / ACTIVITY_WINDOW_DAYS
        suffix = " · _đang đồng bộ_" if syncing else ""
        if matches <= 0:
            return f"{rank} {tier_emoji} **{row['canonical_name']}** — _{tier_label}_{suffix}"
        return (
            f"{rank} {tier_emoji} **{row['canonical_name']}** — "
            f"`{hours:.1f}h` · {matches} trận · {per_day:.1f}h/ngày · _{tier_label}_{suffix}"
        )


_RANK_BADGES = {1: "🥇", 2: "🥈", 3: "🥉"}


def _rank_badge(index: int) -> str:
    return _RANK_BADGES.get(index, f"`#{index:>2}`")


def _addiction_tier(hours: float, matches: int) -> tuple[str, str]:
    if matches <= 0:
        return "😴", "Bỏ game rồi à?"
    if hours > 30:
        return "💀", "Hết thuốc chữa"
    if hours > 15:
        return "🚨", "Nghiện nặng"
    if hours > 5:
        return "🔥", "Phê lắm rồi"
    if hours > 1:
        return "🎮", "Casual"
    return "🌱", "Mới tập"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
