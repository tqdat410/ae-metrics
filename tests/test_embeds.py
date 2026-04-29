from bot.embeds import tier_weight


def test_tier_weight_orders_divisions_and_points():
    assert tier_weight("BRONZE", "IV", 0) < tier_weight("BRONZE", "I", 100)
    assert tier_weight("BRONZE", "I", 100) < tier_weight("SILVER", "IV", 0)


def test_tier_weight_orders_top_tiers():
    assert tier_weight("MASTER", None, 1500) > tier_weight("DIAMOND", None, 500)
    assert tier_weight("Gold", "1", 1) > tier_weight("Gold", "3", 0)
