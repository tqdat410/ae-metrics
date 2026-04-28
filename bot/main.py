from __future__ import annotations

import asyncio
import importlib
import logging
import pkgutil
from logging.handlers import RotatingFileHandler

import discord
from discord.ext import commands

from bot import db, http_client
from bot.config import Settings, get_settings


def setup_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        RotatingFileHandler("bot.log", maxBytes=5 * 1024 * 1024, backupCount=3),
    ]
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


class GameStatsBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.settings = settings
        self.guild_object = discord.Object(id=settings.discord_guild_id)
        self.background_tasks: list[asyncio.Task] = []

    async def setup_hook(self) -> None:
        await db.init(self.settings.db_path)
        await self._load_cogs()
        self.tree.copy_global_to(guild=self.guild_object)
        await self.tree.sync(guild=self.guild_object)

        from bot.key_monitor import monitor_loop
        from bot.providers.pubg_provider import prewarm_current_seasons

        self.background_tasks.extend(
            [
                asyncio.create_task(monitor_loop(self), name="riot-key-monitor"),
                asyncio.create_task(prewarm_current_seasons(["steam"]), name="pubg-season-prewarm"),
            ]
        )

    async def _load_cogs(self) -> None:
        import bot.cogs

        for module in pkgutil.iter_modules(bot.cogs.__path__, bot.cogs.__name__ + "."):
            imported = importlib.import_module(module.name)
            setup = getattr(imported, "setup", None)
            if setup:
                await setup(self)

    async def close(self) -> None:
        for task in self.background_tasks:
            task.cancel()
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        await http_client.close()
        await db.close()
        await super().close()


async def run_bot() -> None:
    settings = get_settings()
    settings.validate_required_secrets()
    setup_logging(settings)
    bot = GameStatsBot(settings)
    async with bot:
        await bot.start(settings.discord_token)


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
