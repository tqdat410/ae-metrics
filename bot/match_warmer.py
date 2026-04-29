from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from bot import db
from bot.providers import account_from_link, get_provider

LOGGER = logging.getLogger(__name__)
PLAYER_BATCH_LIMIT = 10
RECENT_MATCH_LIMIT = 50
WARMER_INTERVAL_SECONDS = 300
_task: asyncio.Task | None = None


def start(_bot: Any, provider: Any | None = None) -> asyncio.Task:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop(provider or get_provider()), name="pubg-match-warmer")
    return _task


async def stop() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    await asyncio.gather(_task, return_exceptions=True)
    _task = None


async def _loop(provider: Any) -> None:
    while True:
        try:
            await tick(provider)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("PUBG match warmer tick failed")
        await asyncio.sleep(WARMER_INTERVAL_SECONDS)


async def tick(provider: Any | None = None) -> None:
    provider = provider or get_provider()
    rows = await db.list_pubg_links()
    if not rows:
        LOGGER.debug("PUBG match warmer skipped: no linked users")
        return

    rows_by_platform: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rows_by_platform[row["platform"]].append(row)

    summaries: list[dict[str, Any]] = []
    cursors: list[tuple[str, str, dict[str, Any]]] = []
    for platform_rows in rows_by_platform.values():
        for chunk in _chunked(platform_rows, PLAYER_BATCH_LIMIT):
            accounts = [account_from_link(row) for row in chunk]
            recent_ids_by_account = await provider.fetch_recent_match_ids_batch(accounts, limit=RECENT_MATCH_LIMIT)
            for account in accounts:
                recent_ids = recent_ids_by_account.get(account.account_id) or []
                for match_id in recent_ids:
                    if await db.match_summary_exists(match_id, account.account_id, account.region):
                        continue
                    summaries.append(await provider.fetch_match_summary(account, match_id))
                cursors.append((account.account_id, account.region, {"fetched_at": _now_unix()}))

    if summaries:
        await db.insert_match_summaries_if_absent(summaries, commit=False)
    if cursors:
        await db.set_match_cursors(cursors, commit=False)
    if summaries or cursors:
        await db.commit()
    LOGGER.info("PUBG match warmer tick complete: links=%s new_matches=%s", len(rows), len(summaries))


def _chunked(items: list[dict], size: int) -> list[list[dict]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _now_unix() -> int:
    return int(datetime.now(timezone.utc).timestamp())
