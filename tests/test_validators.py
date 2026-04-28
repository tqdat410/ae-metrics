import pytest

from bot.validators import parse_riot_id, validate_game, validate_region


def test_parse_riot_id_accepts_valid_name_tag():
    assert parse_riot_id("Faker#KR1") == ("Faker", "KR1")
    assert parse_riot_id("Hide on bush#KR1") == ("Hide on bush", "KR1")


@pytest.mark.parametrize("value", ["NoTag", "A#1", "This Name Is Too Long#VN2", "Name#TOOLONG", "   #VN2"])
def test_parse_riot_id_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        parse_riot_id(value)


def test_validate_game_and_region_defaults():
    assert validate_game("LoL") == "lol"
    assert validate_region("valo", None) == "ap"


def test_validate_region_rejects_unknown_region():
    with pytest.raises(ValueError):
        validate_region("pubg", "stadia")
