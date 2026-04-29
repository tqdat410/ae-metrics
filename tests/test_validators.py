import pytest

from bot.validators import (
    validate_leaderboard_metric,
    validate_platform,
    validate_profile_view,
)


def test_validate_platform_defaults_to_steam():
    assert validate_platform(None) == "steam"
    assert validate_platform("PSN") == "psn"


@pytest.mark.parametrize("value", ["stadia", " pc "])
def test_validate_platform_rejects_unknown_values(value):
    with pytest.raises(ValueError):
        validate_platform(value)


def test_validate_profile_view_defaults_to_ranked():
    assert validate_profile_view(None) == "ranked"
    assert validate_profile_view("Lifetime") == "lifetime"


def test_validate_leaderboard_metric_rejects_unknown_metric():
    with pytest.raises(ValueError):
        validate_leaderboard_metric("elo")
