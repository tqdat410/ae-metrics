import pytest

from bot.validators import (
    validate_platform,
    validate_profile_visibility,
)


def test_validate_platform_defaults_to_steam():
    assert validate_platform(None) == "steam"
    assert validate_platform("PSN") == "psn"


@pytest.mark.parametrize("value", ["stadia", " pc "])
def test_validate_platform_rejects_unknown_values(value):
    with pytest.raises(ValueError):
        validate_platform(value)


def test_validate_profile_visibility_defaults_to_private():
    assert validate_profile_visibility(None) == "private"
    assert validate_profile_visibility("PUBLIC") == "public"


def test_validate_profile_visibility_rejects_unknown_value():
    with pytest.raises(ValueError):
        validate_profile_visibility("friends-only")
