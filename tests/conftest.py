import pytest

from bot import db


@pytest.fixture
async def tmp_db(tmp_path):
    await db.init(str(tmp_path / "bot.db"))
    yield
    await db.close()

