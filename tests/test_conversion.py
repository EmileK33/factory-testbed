"""Conversion against the committed rate table.

Coupled to ``data/rates.json``: a change to the rates moves these expectations.
"""

from src.rates import to_usd_cents


def test_to_usd_cents_converts_with_the_committed_rates():
    assert to_usd_cents(450, "USD") == 45000
    assert to_usd_cents(1200, "EUR") == 129600


def test_jpy_row_converts_at_the_committed_rate():
    # 9800 JPY at 65 bp against USD: 9800 * 65 / 10000 = 63.70 USD = 6370 cents, derived by hand.
    assert to_usd_cents(9800, "JPY") == 6370
