from __future__ import annotations

import asyncio
import time
from collections import defaultdict

INTERVALS = {"pubg": 6.0}

_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_last_seen: dict[str, float] = defaultdict(float)


async def throttle(name: str) -> None:
    base = name.split("_", 1)[0]
    interval = INTERVALS.get(base, 0.1)
    async with _locks[name]:
        now = time.monotonic()
        wait_for = interval - (now - _last_seen[name])
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        _last_seen[name] = time.monotonic()
