from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from bot import cache, db
from bot.config import RECENT_WINDOW
from bot.providers import RateLimitError, account_from_link, get_provider

LOGGER = logging.getLogger(__name__)
ACTIVITY_WINDOW_DAYS = 7
MAX_MATCH_FETCHES_PER_ACCOUNT_PER_TICK = 20
PLAYER_BATCH_LIMIT = 10
WARMER_INTERVAL_SECONDS = 300
STAT_REFRESH_BUFFER_SECONDS = 60
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
    stats_refreshed = 0
    stat_warm_blocked = False
    for platform_rows in rows_by_platform.values():
        for chunk in _chunked(platform_rows, PLAYER_BATCH_LIMIT):
            accounts = [account_from_link(row) for row in chunk]
            recent_ids_by_account = await provider.fetch_recent_match_ids_batch(accounts, limit=None)
            for account in accounts:
                try:
                    state = await _sync_account_matches(
                        provider,
                        account,
                        recent_ids_by_account.get(account.account_id) or [],
                        cutoff_unix=cutoff_unix,
                        fetch_budget=MAX_MATCH_FETCHES_PER_ACCOUNT_PER_TICK,
                    )
                except RateLimitError as exc:
                    LOGGER.warning("PUBG match sync hit rate limit, deferring rest of tick: %s", exc)
                    stat_warm_blocked = True
                    break
                summaries.extend(state["summaries"])
                cursors.append((account.account_id, account.region, state["cursor"]))
                if stat_warm_blocked:
                    continue
                try:
                    stats_refreshed += await _warm_stat_sources(provider, account)
                except RateLimitError as exc:
                    LOGGER.warning("PUBG stat warm hit rate limit, deferring rest of tick: %s", exc)
                    stat_warm_blocked = True

    if summaries:
        await db.insert_match_summaries_if_absent(summaries, commit=False)
    if cursors:
        await db.set_match_cursors(cursors, commit=False)
    if summaries or cursors:
        await db.commit()
    LOGGER.info(
        "PUBG match warmer tick complete: links=%s new_matches=%s stats_refreshed=%s",
        len(rows),
        len(summaries),
        stats_refreshed,
    )


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


async def _warm_stat_sources(provider: Any, account: Any) -> int:
    """Pre-warm ranked/lifetime/mastery/metadata caches before TTL expiry.

    Refreshes only when cache is missing or within STAT_REFRESH_BUFFER_SECONDS
    of expiry, so stat-heavy commands (/profile, /compare) avoid cold-path API.
    """
    refreshed = 0
    season_id = await provider.get_current_season(account.region)
    iso_now = datetime.now(timezone.utc).isoformat()

    ranked_key = f"source-ranked:all:{season_id}"
    if await _stat_needs_refresh(account, ranked_key, ttl=cache.CACHE_TTL["source-ranked:"]):
        payload = await provider.fetch_ranked_view(account, mode="all", season_id=season_id)
        await db.set_cache(account.account_id, account.region, ranked_key, payload)
        await db.upsert_stat_snapshot(account.account_id, account.region, "ranked", iso_now, payload)
        refreshed += 1

    if await _stat_needs_refresh(account, "source-lifetime:all", ttl=cache.CACHE_TTL["source-lifetime:"]):
        payload = await provider.fetch_lifetime_view(account, mode="all")
        await db.set_cache(account.account_id, account.region, "source-lifetime:all", payload)
        await db.upsert_stat_snapshot(account.account_id, account.region, "lifetime", iso_now, payload)
        refreshed += 1

    if await _stat_needs_refresh(account, "source-mastery:v1", ttl=cache.CACHE_TTL["source-mastery:v1"]):
        payload = await provider.fetch_mastery_view(account)
        await db.set_cache(account.account_id, account.region, "source-mastery:v1", payload)
        refreshed += 1

    if await _stat_needs_refresh(account, "source-account", ttl=15 * 60):
        payload = await provider.fetch_account_metadata(account)
        await db.set_cache(account.account_id, account.region, "source-account", payload)
        refreshed += 1

    return refreshed


async def _stat_needs_refresh(account: Any, view: str, *, ttl: int) -> bool:
    cached = await db.get_cache(account.account_id, account.region, view)
    if cached is None:
        return True
    _, age = cached
    return age >= max(ttl - STAT_REFRESH_BUFFER_SECONDS, 0)


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
