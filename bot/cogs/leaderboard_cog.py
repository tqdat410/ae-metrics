from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import discord
from discord.ext import commands

from bot import db
from bot.embeds import make_leaderboard_embed, make_message_embed
from bot.providers import get_provider
from bot.rate_limiter import throttle

LOGGER = logging.getLogger(__name__)
ACTIVITY_WINDOW_DAYS = 7
RECENT_MATCH_LIMIT = 10
PLAYER_BATCH_LIMIT = 10
TOP_ROWS = 10


def _account_from_link(link: dict) -> SimpleNamespace:
    return SimpleNamespace(
        account_id=link["pubg_account_id"],
        canonical_name=link["canonical_name"],
        region=link["platform"],
    )


def _activity_cutoff(days: int = ACTIVITY_WINDOW_DAYS) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")


def _chunked(items: list[dict], size: int) -> list[list[dict]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.provider = get_provider()

    @discord.app_commands.command(name="leaderboard", description="Show the PUBG activity leaderboard for linked members")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            rows = await db.list_pubg_links()
            if not rows:
                await interaction.followup.send(embed=make_message_embed("Leaderboard", "No PUBG links yet."))
                return
            await self._refresh_recent_matches(rows)
            entries = await self._entries(rows)
            await interaction.followup.send(embed=make_leaderboard_embed(entries))
        except Exception:
            LOGGER.exception("Leaderboard failed")
            await interaction.followup.send(
                embed=make_message_embed("Leaderboard failed", "Could not build the PUBG leaderboard right now.", color=0xDC2626)
            )

    async def _entries(self, rows: list[dict]) -> list[str]:
        activity_rows = await db.list_match_activity_since(_activity_cutoff())
        activity_by_account = {
            (item["pubg_account_id"], item["platform"]): item
            for item in activity_rows
            if int(item.get("match_count") or 0) > 0
        }
        ranked = []
        for row in rows:
            activity = activity_by_account.get((row["pubg_account_id"], row["platform"]))
            if not activity:
                continue
            ranked.append((float(activity.get("total_survival_seconds") or 0), row, activity))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [self._line(index, row, activity) for index, (_, row, activity) in enumerate(ranked[:TOP_ROWS], start=1)]

    async def _refresh_recent_matches(self, rows: list[dict]) -> None:
        rows_by_platform: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            rows_by_platform[row["platform"]].append(row)
        for platform_rows in rows_by_platform.values():
            for chunk in _chunked(platform_rows, PLAYER_BATCH_LIMIT):
                await self._refresh_batch(chunk)

    async def _refresh_batch(self, rows: list[dict]) -> None:
        accounts = [_account_from_link(row) for row in rows]
        try:
            await throttle("pubg_matches")
            recent_ids_by_account = await self.provider.fetch_recent_match_ids_batch(accounts, limit=RECENT_MATCH_LIMIT)
        except Exception:
            LOGGER.exception("Falling back to per-account activity refresh for leaderboard")
            recent_ids_by_account = await self._fallback_recent_ids(accounts)
        for account in accounts:
            recent_ids = recent_ids_by_account.get(account.account_id) or []
            if not recent_ids:
                continue
            await self._sync_match_summaries(account, recent_ids)

    async def _fallback_recent_ids(self, accounts: list[SimpleNamespace]) -> dict[str, list[str]]:
        recent_ids_by_account: dict[str, list[str]] = {}
        for account in accounts:
            try:
                await throttle("pubg_matches")
                recent_ids_by_account[account.account_id] = await self.provider.fetch_recent_match_ids(account, limit=RECENT_MATCH_LIMIT)
            except Exception:
                LOGGER.exception("Skipping activity refresh for account_id=%s", account.account_id)
        return recent_ids_by_account

    async def _sync_match_summaries(self, account: SimpleNamespace, recent_ids: list[str]) -> None:
        cursor = await db.get_match_cursor(account.account_id, account.region) or {}
        seen_ids = set(cursor.get("recent_match_ids") or [])
        for match_id in recent_ids:
            if match_id in seen_ids:
                continue
            await db.upsert_match_summary(await self.provider.fetch_match_summary(account, match_id))
        await db.set_match_cursor(
            account.account_id,
            account.region,
            {"recent_match_ids": recent_ids, "fetched_at": int(datetime.now(timezone.utc).timestamp())},
        )

    def _line(self, index: int, row: dict, activity: dict) -> str:
        matches = int(activity.get("match_count") or 0)
        hours = float(activity.get("total_survival_seconds") or 0) / 3600
        return f"`[#{index}]` **{row['canonical_name']}** :: `{hours:.1f}h | {matches} matches`"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
