from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from bot import db
from bot.embeds import make_leaderboard_embed, make_message_embed

LOGGER = logging.getLogger(__name__)
ACTIVITY_WINDOW_DAYS = 7
TOP_ROWS = 10


def _activity_cutoff_unix(days: int = ACTIVITY_WINDOW_DAYS) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.app_commands.command(name="leaderboard", description="Show the PUBG activity leaderboard for linked members")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            rows = await db.list_pubg_links()
            if not rows:
                await interaction.followup.send(embed=make_message_embed("Leaderboard", "No PUBG links yet."))
                return
            entries = await self._entries(rows)
            await interaction.followup.send(embed=make_leaderboard_embed(entries))
        except Exception:
            LOGGER.exception("Leaderboard failed")
            await interaction.followup.send(
                embed=make_message_embed("Leaderboard failed", "Could not build the PUBG leaderboard right now.", color=0xDC2626)
            )

    async def _entries(self, rows: list[dict]) -> list[str]:
        activity_rows = await db.list_match_activity_since_unix(_activity_cutoff_unix())
        activity_by_account = {(item["pubg_account_id"], item["platform"]): item for item in activity_rows}

        active: list[tuple[float, dict, dict]] = []
        inactive: list[tuple[float, dict, dict]] = []
        for row in rows:
            activity = activity_by_account.get((row["pubg_account_id"], row["platform"])) or {
                "match_count": 0,
                "total_survival_seconds": 0,
            }
            score = float(activity.get("total_survival_seconds") or 0)
            bucket = active if int(activity.get("match_count") or 0) > 0 else inactive
            bucket.append((score, row, activity))

        active.sort(key=lambda item: item[0], reverse=True)
        ranked = active[:TOP_ROWS] if len(active) > TOP_ROWS else active + inactive
        return [self._line(index, row, activity) for index, (_, row, activity) in enumerate(ranked, start=1)]

    def _line(self, index: int, row: dict, activity: dict) -> str:
        matches = int(activity.get("match_count") or 0)
        hours = float(activity.get("total_survival_seconds") or 0) / 3600
        return f"`[#{index}]` **{row['canonical_name']}** :: `{hours:.1f}h | {matches} matches`"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
