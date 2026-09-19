"""Conversion against the committed rate table.

Coupled to ``data/rates.json``: a change to the rates moves these expectations
and nothing else in the suite.
"""

from src.rates import to_usd_cents


def test_to_usd_cents_converts_with_the_committed_rates():
    assert to_usd_cents(450, "USD") == 45000
    assert to_usd_cents(1200, "EUR") == 129600
    assert to_usd_cents(9800, "JPY") == 6370
