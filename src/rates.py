"""Currency conversion rates.

Rates are stored as basis points against USD (10000 == 1.00 USD) so that every
figure in the report can be derived with integer arithmetic.
"""

from __future__ import annotations

import json
from pathlib import Path

RATES_PATH = Path(__file__).resolve().parent.parent / "data" / "rates.json"


def load_rates(path: str | Path | None = None) -> dict:
    target = Path(path) if path is not None else RATES_PATH
    try:
        with target.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def get_rate(currency: str, path: str | Path | None = None) -> int | None:
    """Return the basis-point rate for *currency*, or ``None`` if unavailable."""
    return load_rates(path).get(currency)


def to_usd_cents(amount: int, currency: str, path: str | Path | None = None) -> int:
    """Convert *amount* in *currency* to whole USD cents."""
    rate = get_rate(currency, path)
    if rate is None:
        return 0
    return amount * rate // 100
