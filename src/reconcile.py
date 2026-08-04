"""Settlement reconciliation total: what the feed nets to, in USD cents."""

from __future__ import annotations

from src.normalise import apply_fees
from src.rates import to_usd_cents
from src.records import load_records
from src.validate import check_record


def settlement_total_cents(records: list[dict] | None = None) -> int:
    """Return the feed's total settled value, in whole USD cents, net of fees.

    *records* defaults to the committed feed. Each record is passed through
    the feed contract (``check_record``) before anything else runs, so a
    malformed or rejected row contributes nothing rather than raising —
    ``apply_fees`` and ``to_usd_cents`` are only ever given normalised rows.
    """
    raw = load_records() if records is None else records
    accepted = [checked for checked in (check_record(row) for row in raw) if checked]
    settled = apply_fees(accepted)
    return sum(to_usd_cents(row["net"], row["currency"]) for row in settled)
