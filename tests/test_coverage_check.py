"""Every currency the contract accepts must have a conversion rate."""

from src.coverage_check import unrated_currencies


def test_every_contract_currency_has_a_rate():
    assert unrated_currencies() == []
