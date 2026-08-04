"""Reconciliation summary: fee load, settled value, concentration, rejections.

Built entirely from the existing modules (``records``, ``validate``,
``normalise``, ``rates``); none of them are modified here.
"""

from __future__ import annotations

from src.normalise import fee_for
from src.rates import to_usd_cents
from src.records import load_records
from src.validate import check_record


def _round_half_away_from_zero(cents: int) -> int:
    """Round whole cents to whole dollars, a ``.50`` boundary rounding away from zero.

    Not reachable through ``reconciliation_summary()`` today: ``check_record()``
    rejects any record with a negative ``amount``, so every accepted record's
    gross value in USD cents is ``>= 0``, and so is their sum — the negative
    branch below never actually runs from that call site. It is implemented
    and unit-tested directly against this function (see
    ``tests/test_summary.py``) because the issue calls the negative case out by
    name and a future contract change (e.g. allowing credits) must not
    silently regress it. That direct test exercises this function only, and is
    not evidence that ``reconciliation_summary()``'s public behaviour has ever
    taken this branch.
    """
    if cents >= 0:
        return (cents + 50) // 100
    return -((-cents + 50) // 100)


def _gross_cents(row: dict) -> int:
    """The record's settled value in whole USD cents, before any fee."""
    return to_usd_cents(row["amount"], row["currency"])


def _fee_cents(row: dict) -> int:
    """The record's fee in whole USD cents.

    The fee is computed first, in the record's native currency (``fee_for``,
    unmodified from ``src.normalise``) — the same amount ``apply_fees`` would
    charge — and only then converted, per record, with the same helper used
    for the gross amount. Fee application precedes currency conversion, and
    conversion never aggregates across a currency boundary before it happens.
    """
    return to_usd_cents(fee_for(row), row["currency"])


def reconciliation_summary(records: list[dict] | None = None) -> dict:
    """Return the feed's fee load, settled value, concentration and rejections.

    Returns a four-key dict:

    - ``effective_fee_bp``: the fee load the feed bears overall, in whole
      basis points of its gross settled value (truncated toward zero).
    - ``settled_dollars``: the feed's total settled value, in whole US
      dollars (rounded half away from zero from the underlying cents total).
    - ``largest_share_bp``: the share of settled value contributed by the
      single largest settled record, in whole basis points (truncated toward
      zero).
    - ``rejected``: how many records the feed contract rejected.

    *records* defaults to the committed feed (``load_records()``). A failure
    to load or parse the default feed is **not** caught here — it propagates,
    the same as it does for every other consumer of ``load_records`` in this
    repository (e.g. ``report.render_report`` calls it unguarded too). A
    broken feed file is an environment problem the caller needs to see, not a
    data-quality issue for this summary to paper over.

    Malformed elements *inside* an explicitly-passed *records* list are
    handled gracefully: ``check_record`` already tolerates a non-dict element
    (returns ``None``, so it is simply counted as rejected rather than
    raising — see its docstring). *records* itself must be a list per the
    signature; passing something that is not a list or ``None`` is a caller
    contract violation and is left to raise naturally (e.g. a ``TypeError``
    from ``len()``/iteration) rather than being defensively validated here.
    """
    raw = load_records() if records is None else records

    accepted = [row for row in (check_record(item) for item in raw) if row is not None]

    gross_cents = [_gross_cents(row) for row in accepted]
    fee_cents = [_fee_cents(row) for row in accepted]

    total_gross_cents = sum(gross_cents)
    total_fee_cents = sum(fee_cents)
    largest_cents = max(gross_cents, default=0)

    if total_gross_cents == 0:
        effective_fee_bp = 0
        largest_share_bp = 0
    else:
        effective_fee_bp = total_fee_cents * 10000 // total_gross_cents
        largest_share_bp = largest_cents * 10000 // total_gross_cents

    return {
        "effective_fee_bp": effective_fee_bp,
        "settled_dollars": _round_half_away_from_zero(total_gross_cents),
        "largest_share_bp": largest_share_bp,
        "rejected": len(raw) - len(accepted),
    }
