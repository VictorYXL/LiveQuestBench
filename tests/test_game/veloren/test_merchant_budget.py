import pytest

from game.veloren.settlement import purchase_funded


@pytest.mark.parametrize(("coins", "funded"), [(0, False), (9, False), (10, True), (11, True)])
def test_opening_currency_complements_sale_goods_without_spending_reserve(coins, funded):
    spec = {"payment_item": "hide", "payment_reserve": 2,
            "stock_amount": 2, "coin_reserve": 5}
    assert purchase_funded({"hide": 4, "common.items.utility.coins": coins}, spec,
                           product_value=6, payment_value=3.5, coin_value=1) is funded


def test_no_opening_currency_preserves_sale_only_budget():
    spec = {"payment_item": "hide", "payment_reserve": 2,
            "stock_amount": 2, "coin_reserve": 5}
    assert purchase_funded({"hide": 7}, spec, product_value=6, payment_value=3.5, coin_value=1)


@pytest.mark.parametrize(("coins", "funded"), [(13, False), (16, False), (17, True)])
def test_currency_payment_is_not_counted_twice_and_overlapping_reserves_are_retained(coins, funded):
    spec = {"payment_item": "common.items.utility.coins", "payment_reserve": 5,
            "stock_amount": 2, "coin_reserve": 3}
    assert purchase_funded({"common.items.utility.coins": coins}, spec,
                           product_value=6, payment_value=1, coin_value=1) is funded
