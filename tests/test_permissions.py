from types import SimpleNamespace

from bot.permissions import is_admin


def test_is_admin_accepts_configured_admin_id():
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=42, guild_permissions=SimpleNamespace(administrator=False)),
        client=SimpleNamespace(settings=SimpleNamespace(admin_discord_id=42)),
    )
    assert is_admin(interaction) is True


def test_is_admin_accepts_discord_administrator_permission():
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=7, guild_permissions=SimpleNamespace(administrator=True)),
        client=SimpleNamespace(settings=SimpleNamespace(admin_discord_id=None)),
    )
    assert is_admin(interaction) is True
