import pytest

from bot import db


@pytest.fixture(autouse=True)
def env_defaults(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("DISCORD_GUILD_ID", "1")
    monkeypatch.setenv("PUBG_API_KEY", "test-pubg-key")


@pytest.fixture
async def tmp_db(tmp_path):
    await db.init(str(tmp_path / "bot.db"))
    yield
    await db.close()
