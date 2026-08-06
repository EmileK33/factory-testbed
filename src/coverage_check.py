"""Cross-checks between the feed contract and the conversion table.

The contract names the currency codes a record may carry; the rate table names
the currencies a figure can actually be derived for. Nothing keeps the two in
step, so a currency can be admitted by the contract and then silently convert
to zero. This module reports that gap rather than repairing it.
"""

from __future__ import annotations

from src.rates import load_rates
from src.validate import CURRENCY_CODES


def unrated_currencies(path=None) -> list[str]:
    """Contract currencies with no entry in the rate table, in contract order."""
    rates = load_rates(path)
    return [code for code in CURRENCY_CODES if code not in rates]
