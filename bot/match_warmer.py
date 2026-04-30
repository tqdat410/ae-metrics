from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from bot import db
from bot.config import RECENT_WINDOW
from bot.providers import account_from_link, get_provider

LOGGER = logging.getLogger(__name__)
ACTIVITY_WINDOW_DAYS = 7
MAX_MATCH_FETCHES_PER_ACCOUNT_PER_TICK = 20
PLAYER_BATCH_LIMIT = 10
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

    cutoff_unix = _activity_cutoff_unix()
    rows_by_platform: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rows_by_platform[row["platform"]].append(row)

    summaries: list[dict[str, Any]] = []
    cursors: list[tuple[str, str, dict[str, Any]]] = []
    for platform_rows in rows_by_platform.values():
        for chunk in _chunked(platform_rows, PLAYER_BATCH_LIMIT):
            accounts = [account_from_link(row) for row in chunk]
            recent_ids_by_account = await provider.fetch_recent_match_ids_batch(accounts, limit=None)
            for account in accounts:
                state = await _sync_account_matches(
                    provider,
                    account,
                    recent_ids_by_account.get(account.account_id) or [],
                    cutoff_unix=cutoff_unix,
                    fetch_budget=MAX_MATCH_FETCHES_PER_ACCOUNT_PER_TICK,
                )
                summaries.extend(state["summaries"])
                cursors.append((account.account_id, account.region, state["cursor"]))

    if summaries:
        await db.insert_match_summaries_if_absent(summaries, commit=False)
    if cursors:
        await db.set_match_cursors(cursors, commit=False)
    if summaries or cursors:
        await db.commit()
    LOGGER.info("PUBG match warmer tick complete: links=%s new_matches=%s", len(rows), len(summaries))


async def sync_recent_window(provider: Any, account: Any, *, target_recent: int = RECENT_WINDOW) -> list[dict[str, Any]]:
    cutoff_unix = _activity_cutoff_unix()
    recent_ids_by_account = await provider.fetch_recent_match_ids_batch([account], limit=None)
    state = await _sync_account_matches(
        provider,
        account,
        recent_ids_by_account.get(account.account_id) or [],
        cutoff_unix=cutoff_unix,
        fetch_budget=target_recent,
        target_recent=target_recent,
    )
    if state["summaries"]:
        await db.insert_match_summaries_if_absent(state["summaries"], commit=False)
    await db.set_match_cursor(account.account_id, account.region, state["cursor"], commit=False)
    await db.commit()
    return await db.list_recent_match_summaries(account.account_id, account.region, limit=target_recent)


async def _sync_account_matches(
    provider: Any,
    account: Any,
    recent_ids: list[str],
    *,
    cutoff_unix: int,
    fetch_budget: int,
    target_recent: int = RECENT_WINDOW,
) -> dict[str, Any]:
    deduped_ids = list(dict.fromkeys(match_id for match_id in recent_ids if match_id))
    fetched = 0
    scanned = 0
    summaries: list[dict[str, Any]] = []
    covered_until_unix: int | None = None
    full_7d_sync = not deduped_ids

    for match_id in deduped_ids:
        record = await db.get_match_summary_record(match_id, account.account_id, account.region)
        if record is None:
            if fetched >= fetch_budget:
                break
            summary = await provider.fetch_match_summary(account, match_id)
            summaries.append(summary)
            played_at_unix = _played_at_unix(summary.get("played_at"))
            fetched += 1
        else:
            played_at_unix = record.get("played_at_unix")

        scanned += 1
        if played_at_unix is not None:
            covered_until_unix = played_at_unix
            if played_at_unix < cutoff_unix:
                full_7d_sync = True
                break
    else:
        full_7d_sync = True

    known_recent_total = len(deduped_ids)
    stored_recent = await db.list_recent_match_summaries(account.account_id, account.region, limit=target_recent)
    recent_ready = (len(stored_recent) + min(fetched, target_recent)) >= min(target_recent, known_recent_total) if known_recent_total else True

    return {
        "summaries": summaries,
        "cursor": {
            "fetched_at": _now_unix(),
            "recent_head_match_id": deduped_ids[0] if deduped_ids else None,
            "known_recent_total": known_recent_total,
            "recent_ready": recent_ready,
            "full_7d_sync": full_7d_sync,
            "covered_until_unix": covered_until_unix,
            "scanned_match_count": scanned,
        },
    }


def _chunked(items: list[dict], size: int) -> list[list[dict]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _activity_cutoff_unix() -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=ACTIVITY_WINDOW_DAYS)).timestamp())


def _played_at_unix(played_at: Any) -> int | None:
    if not played_at:
        return None
    try:
        return int(datetime.fromisoformat(str(played_at).replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def _now_unix() -> int:
    return int(datetime.now(timezone.utc).timestamp())
