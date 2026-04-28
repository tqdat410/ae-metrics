from __future__ import annotations

import asyncio
import logging
import time

from bot import db

LOGGER = logging.getLogger(__name__)
RIOT_KEY_SET_AT = "riot_key_set_at"
WARN_AFTER_SECONDS = 22 * 60 * 60


async def mark_riot_key_reloaded() -> None:
    await db.set_state(RIOT_KEY_SET_AT, str(int(time.time())))


async def _key_age_seconds() -> int:
    value = await db.get_state(RIOT_KEY_SET_AT)
    if value is None:
        await mark_riot_key_reloaded()
        return 0
    return int(time.time()) - int(value)


async def monitor_loop(bot) -> None:
    while True:
        try:
            admin_id = getattr(bot.settings, "admin_discord_id", None)
            if admin_id and await _key_age_seconds() >= WARN_AFTER_SECONDS:
                user = await bot.fetch_user(admin_id)
                await user.send("Riot dev key is near 24h expiry. Renew it soon, then run `/admin reload-key`.")
        except Exception:
            LOGGER.exception("Riot key monitor failed")
            await asyncio.sleep(300)
            continue
        await asyncio.sleep(3600)
